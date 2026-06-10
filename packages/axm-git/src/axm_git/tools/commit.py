"""GitCommitTool — batched atomic commits with pre-commit handling."""

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
from axm_git.core.identity import author_args, resolve_identity
from axm_git.core.runner import (
    find_git_root,
    not_a_repo_error,
    run_git,
    stage_spec_files,
    timeout_error_result,
)
from axm_git.tools.commit_text import render_failure_text, render_text

__all__ = ["GitCommitTool"]

logger = logging.getLogger(__name__)


def _attempt_commit(
    commit_args: list[str],
    files: list[str],
    git_root: Path,
    *,
    working_dir: Path | None = None,
) -> tuple[bool, bool, str, list[str]]:
    """Attempt commit with auto-retry on pre-commit fix.

    Runs git from *git_root*; *working_dir* (a possible sub-directory of
    the root) is the resolution fallback for the re-stage path.

    Returns:
        (success, retried, output, auto_fixed) where ``auto_fixed`` is the
        list of files modified by the pre-commit hook (captured *before*
        re-staging so it survives the subsequent ``git add``). Empty when
        no auto-fix occurred.
    """
    commit = run_git(commit_args, git_root)
    retried = False
    auto_fixed: list[str] = []

    # If pre-commit auto-fixed files, capture the diff BEFORE re-staging
    # (otherwise ``git diff --name-only`` would be empty after ``git add``).
    if commit.returncode != 0:
        output = commit.stdout + commit.stderr
        if "files were modified by this hook" in output:
            logger.warning("Pre-commit auto-fixed files, re-staging and retrying")
            diff = run_git(["diff", "--name-only"], git_root)
            auto_fixed = [f for f in diff.stdout.strip().splitlines() if f.strip()]
            stage_spec_files(files, git_root, working_dir=working_dir)
            commit = run_git(commit_args, git_root)
            retried = True

    output = commit.stdout + commit.stderr
    return commit.returncode == 0, retried, output, auto_fixed


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
    """Validate a single commit spec, returning a ToolResult error or None."""
    if not spec.get("files"):
        return _validation_failure(
            error=f"Commit {index}: empty files list",
            results=results,
            total=total,
        )
    if not spec.get("message"):
        return _validation_failure(
            error=f"Commit {index}: empty message",
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
) -> dict[str, object]:
    """Build failure data dict for a failed commit.

    *auto_fixed* is the list of files captured by ``_attempt_commit``
    before re-staging — we no longer recompute it here because the
    subsequent ``git add`` would have emptied the diff.
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
        },
    }


def _process_single_commit(  # noqa: PLR0913
    spec: dict[str, object],
    index: int,
    identity_args: list[str],
    path: Path,
    results: list[dict[str, object]],
    total: int,
    *,
    strict: bool = False,
) -> ToolResult | None:
    """Process one commit spec: validate, stage, commit, record result.

    Returns a ``ToolResult`` on failure or ``None`` on success
    (appending the commit record to *results*).
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
        error = f"Commit {index}: pre-commit failed"
        data = _build_failure_data(
            results,
            index=index,
            message=message,
            output=output,
            retried=retried,
            auto_fixed=auto_fixed,
            total=total,
        )
        return ToolResult(
            success=False,
            error=error,
            data=data,
            text=render_failure_text(error=error, data=data),
        )

    # Get the SHA of the commit
    log = run_git(["log", "-1", "--format=%H"], git_root)
    sha = log.stdout.strip()[:7]

    results.append(
        {
            "sha": sha,
            "message": message,
            "precommit_passed": True,
            "retried": retried,
        }
    )
    return None


class GitCommitTool(AXMTool):
    """Execute one or more atomic commits in a single call.

    Each commit in the batch is processed sequentially: stage files,
    run ``git commit`` (pre-commit hooks fire automatically), and
    capture the result.  If a commit fails (e.g. pre-commit rejects),
    processing stops and the error is returned alongside any commits
    that already succeeded.

    When a pre-commit hook auto-fixes files (e.g. ruff ``--fix``),
    the tool automatically re-stages and retries the commit once.

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
            ToolResult with list of committed results and an
            ``author`` key (``{name, email}`` or ``None``).
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

            for i, spec in enumerate(commit_list):
                failure = _process_single_commit(
                    spec, i + 1, identity_args, resolved, results, total, strict=strict
                )
                if failure:
                    return failure
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        data = {
            "results": results,
            "total": len(results),
            "succeeded": len(results),
            "author": (
                {"name": identity.name, "email": identity.email} if identity else None
            ),
        }
        return ToolResult(success=True, data=data, text=render_text(data))
