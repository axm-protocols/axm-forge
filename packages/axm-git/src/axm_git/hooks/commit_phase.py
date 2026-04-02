"""Commit-phase hook action.

Stages all changes and commits with ``[axm] {phase_name}``.
Supports a ``from_outputs`` mode that reads ``commit_spec``
from context for targeted file staging.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from axm.hooks.base import HookResult

from axm_git.core.runner import find_git_root, run_git

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
    Gitignored files are skipped with a warning appended to *warnings*.
    Missing files produce a clear diagnostic error.
    """
    for filepath in files:
        full = git_root / filepath
        if not full.exists():
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
) -> list[str]:
    """Build the ``git commit`` argument list."""
    cmd = ["commit", "-m", message]
    if body:
        cmd.extend(["-m", body])
    if skip_hooks:
        cmd.append("--no-verify")
    return cmd


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

        if params.get("from_outputs"):
            skip_hooks = params.get("skip_hooks", True)
            return self._commit_from_outputs(
                context, working_dir, skip_hooks=skip_hooks
            )

        return self._commit_legacy(context, working_dir, **params)

    def _commit_legacy(
        self,
        context: dict[str, Any],
        working_dir: Path,
        **params: Any,
    ) -> HookResult:
        """Legacy mode: stage all and commit with format string."""
        phase_name: str = context["phase_name"]

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
        result = run_git(["commit", "-m", msg], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git commit failed: {result.stderr}")

        # Get commit hash
        hash_result = run_git(["rev-parse", "--short", "HEAD"], working_dir)
        return HookResult.ok(commit=hash_result.stdout.strip(), message=msg)

    def _commit_from_outputs(
        self,
        context: dict[str, Any],
        working_dir: Path,
        *,
        skip_hooks: bool = True,
    ) -> HookResult:
        """Outputs mode: read commit_spec from context, stage listed files.

        If the commit fails because pre-commit hooks auto-fixed files
        (stderr contains ``"files were modified"``), the listed files are
        re-staged and the commit is retried once.
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

        warnings: list[str] = []
        stage_err = _stage_spec_files(files, git_root, warnings=warnings)
        if stage_err:
            return HookResult.fail(stage_err)

        # Check if there's anything to commit
        status = run_git(["diff", "--cached", "--name-only"], git_root)
        if not status.stdout.strip():
            return HookResult.ok(skipped=True, reason="nothing to commit")

        commit_cmd = _build_commit_cmd(message, body, skip_hooks=skip_hooks)

        result = run_git(commit_cmd, git_root)
        if result.returncode != 0:
            result = _retry_commit_on_autofix(files, commit_cmd, git_root, result)
            if result.returncode != 0:
                return HookResult.fail(f"git commit failed: {result.stderr}")

        # Get commit hash
        hash_result = run_git(["rev-parse", "--short", "HEAD"], git_root)
        result_kw: dict[str, Any] = {
            "commit": hash_result.stdout.strip(),
            "message": message,
        }
        if warnings:
            result_kw["warnings"] = warnings
        return HookResult.ok(**result_kw)
