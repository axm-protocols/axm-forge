"""GitBranchTool — create or checkout git branches."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import not_a_repo_error, run_git, timeout_error_result
from axm_git.tools.branch_text import render_failure_text, render_text

__all__ = ["GitBranchTool"]


class GitBranchTool(AXMTool):
    """Create or checkout a git branch in one call.

    Registered as ``git_branch`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_branch"

    def execute(  # type: ignore[override]
        self,
        *,
        name: str,
        from_ref: str | None = None,
        checkout_only: bool = False,
        delete: bool = False,
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Create, checkout, or delete a git branch.

        Args:
            name: Branch name (required).
            from_ref: Optional ref to branch from (tag, commit, branch).
            checkout_only: If True, checkout existing branch without creating.
            delete: If True, delete the branch (``git branch -D``) instead of
                creating/checking out. Mutually exclusive with the create path.
            path: Project root directory.

        Returns:
            ToolResult with branch name on success.
        """
        resolved = Path(path).resolve()

        try:
            # Verify this is a git repo.
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

            if delete:
                return self._delete(name, resolved)

            # Build the checkout command.
            if checkout_only:
                cmd = ["checkout", name]
            else:
                cmd = ["checkout", "-b", name]
                if from_ref is not None:
                    cmd.append(from_ref)

            result = run_git(cmd, resolved)
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return ToolResult(
                    success=False,
                    error=error,
                    text=render_failure_text(error=error, data=None),
                )

            # Confirm the current branch.
            current = run_git(["branch", "--show-current"], resolved)
            branch = current.stdout.strip()
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        data: dict[str, object] = {"branch": branch}
        return ToolResult(success=True, data=data, text=render_text(data))

    @staticmethod
    def _delete(name: str, resolved: Path) -> ToolResult:
        """Delete branch *name* via ``git branch -D``."""
        result = run_git(["branch", "-D", name], resolved)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return ToolResult(
                success=False,
                error=error,
                text=render_failure_text(error=error, data=None),
            )
        data: dict[str, object] = {"branch": name, "deleted": True}
        return ToolResult(
            success=True, data=data, text=f"git_branch | ✓ | deleted {name}"
        )
