"""Commit-phase hook action.

Stages all changes and commits with ``[axm] {phase_name}``.
Supports a ``from_outputs`` mode that reads ``commit_spec``
from context for targeted file staging.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from axm.hooks.base import HookResult

from axm_git.core.identity import (  # noqa: F401 (author_args: mock target)
    author_args,
    resolve_identity,
)
from axm_git.core.runner import find_git_root, run_git

logger = logging.getLogger(__name__)

__all__ = ["CommitPhaseHook"]

_REQUIRED_SPEC_KEYS = {"message", "files"}


def _validate_commit_spec(
    spec: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a ``commit_spec`` dict.

    Returns:
        (spec, error_message) — spec is None when error is set.
    """
    if not spec:
        return None, "from_outputs=True but no commit_spec in context"
    if not isinstance(spec, dict):
        return None, "commit_spec must be a dict"
    missing = _REQUIRED_SPEC_KEYS - set(spec)
    if missing:
        return None, (
            f"commit_spec missing {', '.join(repr(k) for k in sorted(missing))}"
        )
    return spec, None


def _stage_spec_files(
    files: list[str],
    git_root: Path,
    *,
    warnings: list[str] | None = None,
) -> str | None:
    """Stage each file in *files*, returning an error message on failure.

    Paths in *files* are expected relative to *git_root*.
    Tracked-but-deleted files (git status ``D``) are staged as deletions.
    Gitignored files are skipped with a warning appended to *warnings*.
    Truly missing files (never tracked) produce a clear diagnostic error.
    """
    for filepath in files:
        full = git_root / filepath
        if not full.exists():
            # Check if the file is tracked-but-deleted (git status D)
            ls_result = run_git(["ls-files", "-d", filepath], git_root)
            if not ls_result.stdout.strip():
                return f"files not found: {filepath}"
        add_result = run_git(["add", filepath], git_root)
        if add_result.returncode != 0:
            if "ignored" in add_result.stderr.lower():
                if warnings is not None:
                    warnings.append(f"skipped gitignored file: {filepath}")
                continue
            return f"git add failed for {filepath}: {add_result.stderr}"
    return None


def _build_commit_cmd(
    message: str,
    body: str | None,
    *,
    skip_hooks: bool = True,
    author: str | None = None,
) -> list[str]:
    """Build the ``git commit`` argument list.

    Args:
        message: Commit summary line.
        body: Optional extended commit body.
        skip_hooks: Append ``--no-verify`` when *True*.
        author: Git ``--author`` value (``"Name <email>"``).
            When *None*, git uses the default identity.
    """
    cmd = ["commit", "-m", message]
    if body:
        cmd.extend(["-m", body])
    if skip_hooks:
        cmd.append("--no-verify")
    if author:
        cmd.append(f"--author={author}")
    return cmd


def _format_spec_files(files: list[str], git_root: Path) -> None:
    """Run ``ruff check --fix`` then ``ruff format`` on *files*.

    Non-fatal: logs warnings on failure but never raises.
    Resolves paths relative to *git_root* before passing to ruff.
    """
    targets = [str(git_root / f) for f in files if f.endswith(".py")]
    if not targets:
        return

    for cmd in (
        ["ruff", "check", "--fix", *targets],
        ["ruff", "format", *targets],
    ):
        try:
            subprocess.run(
                cmd,
                cwd=git_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            logger.debug("ruff not found, skipping pre-commit format")
            return


def _build_commit_result(
    git_root: Path,
    message: str,
    identity: Any,
    warnings: list[str],
) -> HookResult:
    """Build a successful commit :class:`HookResult`.

    Reads the current HEAD short hash and assembles the result dict
    with optional identity and warning fields.
    """
    hash_result = run_git(["rev-parse", "--short", "HEAD"], git_root)
    result_kw: dict[str, Any] = {
        "commit": hash_result.stdout.strip(),
        "message": message,
    }
    if identity:
        result_kw["author_name"] = identity.name
        result_kw["author_email"] = identity.email
    if warnings:
        result_kw["warnings"] = warnings
    return HookResult.ok(**result_kw)


def _retry_commit_on_autofix(
    files: list[str],
    cmd: list[str],
    git_root: Path,
    first_result: Any,
) -> Any:
    """Handle pre-commit autofix retry for a failed commit.

    If *first_result* stderr contains ``"files were modified"``, re-stage
    *files* and retry the commit once.  Otherwise return *first_result*
    unchanged.

    Returns a GitResult-like object (has *returncode*, *stdout*, *stderr*).
    """
    if "files were modified" not in first_result.stderr:
        return first_result
    restage_err = _stage_spec_files(files, git_root)
    if restage_err:
        from types import SimpleNamespace

        return SimpleNamespace(returncode=1, stdout="", stderr=restage_err)
    return run_git(cmd, git_root)


@dataclass
class CommitPhaseHook:
    """Commit all changes with message ``[axm] {phase_name}``.

    Reads ``phase_name`` from *context*.  An optional
    ``message_format`` can be provided via *params*
    (default ``"[axm] {phase}"``).  Skips gracefully when
    there is nothing to commit or no git repository.

    When ``from_outputs=True`` is passed in *params*, reads
    ``commit_spec`` from *context* instead: ``{message, body?, files}``.
    Only the listed files are staged (no ``git add -A``).
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``message_format``, ``from_outputs``,
                ``working_dir``, ``skip_hooks`` (default ``True`` for
                ``from_outputs`` mode — appends ``--no-verify``).

        Returns:
            HookResult with ``commit`` hash and ``message`` in metadata.
        """
        working_dir = Path(params.get("working_dir", context.get("working_dir", ".")))

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if find_git_root(working_dir) is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        profile: str | None = params.pop("profile", None)

        if params.get("from_outputs"):
            skip_hooks = params.get("skip_hooks", True)
            return self._commit_from_outputs(
                context, working_dir, skip_hooks=skip_hooks, profile=profile
            )

        return self._commit_legacy(context, working_dir, profile=profile, **params)

    def _commit_legacy(
        self,
        context: dict[str, Any],
        working_dir: Path,
        *,
        profile: str | None = None,
        **params: Any,
    ) -> HookResult:
        """Legacy mode: stage all changes and commit with a format string.

        Resolves the author identity via :func:`resolve_identity` and
        injects ``--author`` into the commit command when a profile is
        found.  Identity metadata (name, email) is included in the
        returned :class:`HookResult`.

        Args:
            context: Session context containing ``phase_name``.
            working_dir: Repository working directory.
            profile: Optional identity profile name override.
            **params: Extra params; ``message_format`` controls the
                commit message template (default ``"[axm] {phase}"``).
        """
        phase_name: str = context["phase_name"]

        # Resolve author identity
        identity = resolve_identity(working_dir, profile_override=profile)
        author = f"{identity.name} <{identity.email}>" if identity else None

        # Stage all changes (scoped to working_dir for workspace layouts)
        run_git(["add", "-A", "."], working_dir)

        # Check if there's anything to commit
        status = run_git(["status", "--porcelain", "--", "."], working_dir)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        # Commit
        msg = params.get("message_format", "[axm] {phase}").format(
            phase=phase_name,
        )
        commit_cmd = _build_commit_cmd(msg, None, author=author)
        result = run_git(commit_cmd, working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git commit failed: {result.stderr}")

        # Get commit hash
        hash_result = run_git(["rev-parse", "--short", "HEAD"], working_dir)
        result_kw: dict[str, Any] = {
            "commit": hash_result.stdout.strip(),
            "message": msg,
        }
        if identity:
            result_kw["author_name"] = identity.name
            result_kw["author_email"] = identity.email
        return HookResult.ok(**result_kw)

    def _commit_from_outputs(
        self,
        context: dict[str, Any],
        working_dir: Path,
        *,
        skip_hooks: bool = True,
        profile: str | None = None,
    ) -> HookResult:
        """Outputs mode: read ``commit_spec`` from context, stage listed files.

        Resolves the author identity via :func:`resolve_identity` and
        injects ``--author`` into the commit command when a profile is
        found.  If the commit fails because pre-commit hooks auto-fixed
        files (stderr contains ``"files were modified"``), the listed
        files are re-staged and the commit is retried once.

        Args:
            context: Session context containing ``commit_spec``.
            working_dir: Repository working directory.
            skip_hooks: Append ``--no-verify`` to the commit command.
            profile: Optional identity profile name override.
        """
        spec, err = _validate_commit_spec(context.get("commit_spec"))
        if err:
            return HookResult.fail(err)
        # spec is guaranteed non-None when err is None
        spec = cast("dict[str, Any]", spec)

        files: list[str] = spec["files"]
        message: str = spec["message"]
        body: str | None = spec.get("body")

        git_root = find_git_root(working_dir) or working_dir

        # Resolve author identity
        identity = resolve_identity(git_root, profile_override=profile)
        author = f"{identity.name} <{identity.email}>" if identity else None

        _format_spec_files(files, git_root)

        warnings: list[str] = []
        stage_err = _stage_spec_files(files, git_root, warnings=warnings)
        if stage_err:
            return HookResult.fail(stage_err)

        # Check if there's anything to commit
        status = run_git(["diff", "--cached", "--name-only"], git_root)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        commit_cmd = _build_commit_cmd(
            message, body, skip_hooks=skip_hooks, author=author
        )

        result = run_git(commit_cmd, git_root)
        if result.returncode != 0:
            result = _retry_commit_on_autofix(files, commit_cmd, git_root, result)
            if result.returncode != 0:
                return HookResult.fail(f"git commit failed: {result.stderr}")

        return _build_commit_result(git_root, message, identity, warnings)
