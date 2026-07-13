"""GitCommitTool — batched atomic commits with commit-hook handling."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.branch_naming import (
    CONVENTIONAL_COMMIT_FORMAT,
    is_conventional_commit,
)
from axm_git.core.commit_spec import (
    attempt_commit_with_autofix_retry,
    validate_commit_spec,
)
from axm_git.core.identity import author_args, resolve_identity
from axm_git.core.runner import (
    find_git_root,
    not_a_repo_error,
    reset_paths,
    run_git,
    stage_spec_files,
    staged_delta,
    timeout_error_result,
)
from axm_git.tools.commit_text import render_failure_text, render_text

__all__ = ["GitCommitTool"]

logger = logging.getLogger(__name__)


def _snapshot_staged(git_root: Path) -> set[str]:
    """Return the set of staged paths (``git diff --cached --name-only``).

    Snapshots the index so the delta a staging operation introduces can be
    computed (:func:`axm_git.core.runner.staged_delta`) and, on a definitive
    hook refusal, scoped-reset without touching third-party staged paths.
    Runs through this module's ``run_git`` so callers stay git-root-relative.
    """
    result = run_git(["diff", "--cached", "--name-only"], git_root)
    return {line for line in result.stdout.splitlines() if line.strip()}


def _attempt_commit(
    commit_args: list[str],
    files: list[str],
    git_root: Path,
    *,
    working_dir: Path | None = None,
) -> tuple[bool, bool, str, list[str]]:
    """Attempt commit with auto-retry on a commit-hook fix.

    Runs git from *git_root*; *working_dir* (a possible sub-directory of
    the root) is the resolution fallback for the re-stage path.

    Returns:
        (success, retried, output, auto_fixed) where ``auto_fixed`` is the
        list of files modified by the commit hook (captured *before*
        re-staging so it survives the subsequent ``git add``). Empty when
        no auto-fix occurred.
    """
    first = run_git(commit_args, git_root)
    retry = attempt_commit_with_autofix_retry(
        commit_args, files, git_root, first, working_dir=working_dir
    )
    commit = retry.result
    output = commit.stdout + commit.stderr
    return commit.returncode == 0, retry.retried, output, retry.auto_fixed


def _validation_failure(
    *, error: str, results: list[dict[str, object]], total: int
) -> ToolResult:
    """Build a validation/staging ``ToolResult`` with consistent text."""
    data = {"results": results, "total": total, "succeeded": len(results)}
    return ToolResult(
        success=False,
        error=error,
        data=data,
        text=render_failure_text(error=error, data=data),
    )


def _validate_commit_spec(
    spec: dict[str, object],
    index: int,
    results: list[dict[str, object]],
    total: int,
    *,
    strict: bool = False,
) -> ToolResult | None:
    """Validate a single commit spec, returning a ToolResult error or None.

    Delegates the structural check to the shared core validator
    (:func:`axm_git.core.commit_spec.validate_commit_spec`) and wraps any
    error in this surface's indexed ``ToolResult`` shape; the
    Conventional-Commit guardrail (warn/strict) stays tool-specific.
    """
    _valid, err = validate_commit_spec(spec)
    if err:
        return _validation_failure(
            error=f"Commit {index}: {err}",
            results=results,
            total=total,
        )
    return _check_conventional(spec, index, results, total, strict=strict)


def _check_conventional(
    spec: dict[str, object],
    index: int,
    results: list[dict[str, object]],
    total: int,
    *,
    strict: bool,
) -> ToolResult | None:
    """Validate Conventional Commit format: warn by default, block if strict.

    Returns a ``ToolResult`` error only when *strict* is enabled and the
    message is non-conventional; otherwise emits a warning and returns
    ``None`` so the commit proceeds (warn-by-default guardrail).
    """
    message = cast("str", spec["message"])
    if is_conventional_commit(message):
        return None

    detail = (
        f"Commit {index}: message {message!r} is not a Conventional Commit "
        f"(expected {CONVENTIONAL_COMMIT_FORMAT!r})"
    )
    if strict:
        return _validation_failure(error=detail, results=results, total=total)
    logger.warning("%s — committing anyway (warn-by-default)", detail)
    return None


def _build_failure_data(  # noqa: PLR0913
    results: list[dict[str, object]],
    *,
    index: int,
    message: str,
    output: str,
    retried: bool,
    auto_fixed: list[str],
    total: int,
    index_restored: bool = False,
    restored_paths: list[str] | None = None,
) -> dict[str, object]:
    """Build failure data dict for a failed commit.

    *auto_fixed* is the list of files captured by ``_attempt_commit``
    before re-staging — we no longer recompute it here because the
    subsequent ``git add`` would have emptied the diff.

    *index_restored* / *restored_paths* record whether the operation's
    staging delta was scoped-reset after a definitive hook refusal (audit
    traceability for AC4).
    """
    return {
        "results": results,
        "total": total,
        "succeeded": len(results),
        "failed_commit": {
            "index": index,
            "message": message,
            "precommit_output": output.strip(),
            "auto_fixed_files": auto_fixed,
            "retried": retried,
            "index_restored": index_restored,
            "restored_paths": restored_paths or [],
        },
    }


def _process_single_commit(  # noqa: PLR0913
    spec: dict[str, object],
    index: int,
    identity_args: list[str],
    path: Path,
    results: list[dict[str, object]],
    total: int,
    autofixed: list[str],
    *,
    strict: bool = False,
) -> ToolResult | None:
    """Process one commit spec: validate, stage, commit, record result.

    Returns a ``ToolResult`` on failure or ``None`` on success
    (appending the commit record to *results*). On the success path any
    hook-mutated file paths captured during the autofix-retry are appended
    to *autofixed* so the caller can surface them at the top level
    (``hook_autofixed_files`` — the Verdict-Carrying Patch invariant).
    """
    validation_err = _validate_commit_spec(spec, index, results, total, strict=strict)
    if validation_err:
        return validation_err

    files = cast("list[str]", spec["files"])
    message = cast("str", spec["message"])
    body = cast("str | None", spec.get("body"))

    # Resolve the git root from the given path: stage and commit relative to
    # the root, while *path* (which may be a sub-directory of the root, e.g. a
    # package directory) is the working-dir fallback for path resolution.
    git_root = find_git_root(path)
    if git_root is None:
        return _validation_failure(
            error=f"Commit {index}: not a git repository: {path}",
            results=results,
            total=total,
        )

    # Snapshot the index BEFORE staging so we can compute the exact delta this
    # operation introduces (third-party staged paths are excluded from it).
    staged_before = _snapshot_staged(git_root)

    # Stage files via the subdir-aware resolver (git-root-relative paths work
    # even when *path* is a package subdir; deletions and gitignored files are
    # handled the same way the commit-phase hook handles them).
    add_err = stage_spec_files(files, git_root, working_dir=path)
    if add_err:
        return _validation_failure(
            error=f"Commit {index}: git add failed: {add_err}",
            results=results,
            total=total,
        )

    # The paths this operation staged (delta vs the pre-call index) — the only
    # paths a definitive-failure restore is allowed to unstage (AC1/AC2).
    recorded = staged_delta(staged_before, _snapshot_staged(git_root))

    # Build commit command
    commit_args = ["commit", "-m", message]
    if body:
        commit_args.extend(["-m", body])
    commit_args.extend(identity_args)

    # Attempt commit with auto-retry
    ok, retried, output, auto_fixed = _attempt_commit(
        commit_args, files, git_root, working_dir=path
    )

    if not ok:
        # Definitive refusal (post auto-fix retry): scoped-reset only the paths
        # this operation staged, leaving the index otherwise as it was (AC1/AC2).
        restored = bool(recorded)
        if restored:
            reset_paths(recorded, git_root)
        error = "Commit {i}: hook check failed{r}".format(
            i=index, r=" (index restored)" if restored else ""
        )
        data = _build_failure_data(
            results,
            index=index,
            message=message,
            output=output,
            retried=retried,
            auto_fixed=auto_fixed,
            total=total,
            index_restored=restored,
            restored_paths=recorded,
        )
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )

    # The commit landed. Record any hook-mutated paths captured during the
    # autofix-retry (empty on the clean path) so the caller surfaces them.
    autofixed.extend(auto_fixed)

    # Get the SHA of the commit
    log = run_git(["log", "-1", "--format=%H"], git_root)
    sha = log.stdout.strip()[:7]

    results.append(
        {
            "sha": sha,
            "message": message,
            # NOTE(deprecation): runner-agnostic key. Kept as
            # ``precommit_passed`` to avoid breaking GitCommitTool
            # consumers; a future ticket renames it to ``hooks_passed``
            # (breaking change).
            "precommit_passed": True,
            "retried": retried,
        }
    )
    return None


class GitCommitTool(AXMTool):
    """Execute one or more atomic commits in a single call.

    Each commit in the batch is processed sequentially: stage files,
    run ``git commit`` (the repo's commit hooks fire automatically), and
    capture the result.  If a commit fails (e.g. a hook rejects it),
    processing stops and the error is returned alongside any commits
    that already succeeded.

    When a commit hook auto-fixes files (e.g. ruff ``--fix``),
    the tool automatically re-stages and retries the commit once.

    **Verdict-Carrying Patch invariant** — when a hook mutates staged
    content on the autofix-retry path, ``ToolResult.data`` reports exactly
    which files changed under ``hook_autofixed_files: list[str]`` (repo-root
    relative). The field is *always present*: it is an empty list on the
    clean path (no hooks, or no mutation) and never ``None``. This lets a
    consumer see that the patch it committed is not byte-for-byte the patch
    it staged — the commit still carries a truthful verdict of what landed.

    The hook runner is whatever the repo installs at
    ``.git/hooks/pre-commit`` (pre-commit OR prek); axm-git never
    invokes the runner directly — git does.

    Registered as ``git_commit`` via axm.tools entry point.
    """

    expose_directly = True
    domain = "git"
    tags = frozenset({"commit", "stage", "conventional"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_commit"

    def execute(
        self,
        *,
        path: str = ".",
        commits: list[dict[str, object]] | None = None,
        profile: str | None = None,
        strict: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Execute batched commits.

        Args:
            path: Project root (required).
            commits: List of commit specs, each a dict with keys:
                - ``files`` (list[str]): Files to stage.
                - ``message`` (str): Commit summary line.
                - ``body`` (str, optional): Commit body.
            profile: Optional identity profile name. Overrides
                schedule-based resolution from ``git-profiles.toml``.
            strict: When ``True``, a non-Conventional-Commit message is a
                hard failure instead of a warning. Defaults to ``False``
                (warn-by-default guardrail).

        Returns:
            ToolResult with a list of committed results, an ``author`` key
            (``{name, email}`` or ``None``), and ``hook_autofixed_files``
            (``list[str]``, repo-root relative) naming any staged files a
            commit hook mutated during the autofix-retry — always present,
            ``[]`` when no hook auto-fixed anything.
        """
        resolved = Path(path).resolve()
        commit_list: list[dict[str, object]] = commits or []
        total = len(commit_list)

        if not commit_list:
            error = "No commits provided"
            return ToolResult(
                success=False,
                error=error,
                text=render_failure_text(error=error, data=None),
            )

        try:
            # Fail fast with suggestions if not a git repo
            check = run_git(["rev-parse", "--git-dir"], resolved)
            if check.returncode != 0:
                repo_err = not_a_repo_error(check.stderr, resolved)
                return ToolResult(
                    success=repo_err.success,
                    error=repo_err.error,
                    data=repo_err.data,
                    text=render_failure_text(
                        error=repo_err.error or "", data=repo_err.data
                    ),
                )

            # Resolve identity once for the entire batch
            identity = resolve_identity(resolved, profile_override=profile)
            identity_args = author_args(identity)

            results: list[dict[str, object]] = []
            autofixed: list[str] = []

            for i, spec in enumerate(commit_list):
                failure = _process_single_commit(
                    spec,
                    i + 1,
                    identity_args,
                    resolved,
                    results,
                    total,
                    autofixed,
                    strict=strict,
                )
                if failure:
                    return failure
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        data = {
            "results": results,
            "total": len(results),
            "succeeded": len(results),
            # Verdict-Carrying Patch invariant: the paths a commit hook
            # auto-fixed during the re-stage + retry (deduplicated, sorted);
            # always present, ``[]`` on the clean path (AC1/AC2).
            "hook_autofixed_files": sorted(set(autofixed)),
            "author": (
                {"name": identity.name, "email": identity.email} if identity else None
            ),
        }
        return ToolResult(success=True, data=data, text=render_text(data))
