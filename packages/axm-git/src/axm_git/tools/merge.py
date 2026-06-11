"""GitMergeTool — squash-merge a branch into a target branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.identity import author_args, resolve_identity
from axm_git.core.runner import not_a_repo_error, run_git, timeout_error_result
from axm_git.tools.merge_text import render_failure_text, render_text

__all__ = ["GitMergeTool"]


def _run_step(args: list[str], cwd: Path, label: str) -> ToolResult | None:
    """Run a git step; return a failure ToolResult, or None on success."""
    result = run_git(args, cwd)
    if result.returncode == 0:
        return None
    error = result.stderr.strip() or result.stdout.strip()
    return ToolResult(
        success=False,
        error=f"{label} failed: {error}",
        text=render_failure_text(error=error),
    )


class GitMergeTool(AXMTool):
    """Squash-merge a branch into a target branch and commit.

    Checks out *target_branch*, runs ``git merge --squash <branch>``, then
    commits the squashed changes (honouring the identity-profile system).
    Registered as ``git_merge`` via axm.tools entry point.
    """

    domain = "git"
    tags = frozenset({"merge", "squash", "branch"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_merge"

    def execute(  # type: ignore[override]
        self,
        *,
        branch: str,
        target_branch: str = "main",
        message: str | None = None,
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Squash-merge *branch* into *target_branch*.

        Args:
            branch: The branch to merge in (required).
            target_branch: The branch to merge into (default ``main``).
            message: Commit message for the squash commit. Defaults to
                ``Merge <branch> (squash)``.
            path: Repository path.

        Returns:
            ToolResult with ``merged``, ``into`` and ``message`` on success.
        """
        resolved = Path(path).resolve()
        msg = message or f"Merge {branch} (squash)"
        try:
            check = run_git(["rev-parse", "--git-dir"], resolved)
            if check.returncode != 0:
                repo_err = not_a_repo_error(check.stderr, resolved)
                return ToolResult(
                    success=repo_err.success,
                    error=repo_err.error,
                    data=repo_err.data,
                    text=render_failure_text(error=repo_err.error or ""),
                )

            identity = resolve_identity(resolved)
            steps = [
                (["checkout", target_branch], f"checkout {target_branch}"),
                (["merge", "--squash", branch], "merge --squash"),
                (["commit", "-m", msg, *author_args(identity)], "commit"),
            ]
            for args, label in steps:
                failure = _run_step(args, resolved, label)
                if failure is not None:
                    return failure
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        data: dict[str, object] = {
            "merged": branch,
            "into": target_branch,
            "message": msg,
        }
        return ToolResult(success=True, data=data, text=render_text(data))
