"""GitBranchTool — create or checkout git branches."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import not_a_repo_error, run_git

__all__ = ["GitBranchTool"]


class GitBranchTool(AXMTool):
    """Create or checkout a git branch in one call.

    Registered as ``git_branch`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_branch"

    def execute(  # type: ignore[override]  # Tool accepts specific args instead of generic kwargs
        self,
        *,
        name: str,
        from_ref: str | None = None,
        checkout_only: bool = False,
        path: str = ".",
        **kwargs: Any,
    ) -> ToolResult:
        """Create or checkout a git branch.

        Args:
            name: Branch name (required).
            from_ref: Optional ref to branch from (tag, commit, branch).
            checkout_only: If True, checkout existing branch without creating.
            path: Project root directory.

        Returns:
            ToolResult with branch name on success.
        """
        resolved = Path(path).resolve()

        # Verify this is a git repo.
        check = run_git(["rev-parse", "--git-dir"], resolved)
        if check.returncode != 0:
            return not_a_repo_error(check.stderr, resolved)

        # Build the checkout command.
        if checkout_only:
            cmd = ["checkout", name]
        else:
            cmd = ["checkout", "-b", name]
            if from_ref is not None:
                cmd.append(from_ref)

        result = run_git(cmd, resolved)
        if result.returncode != 0:
            return ToolResult(
                success=False,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        # Confirm the current branch.
        current = run_git(["branch", "--show-current"], resolved)
        branch = current.stdout.strip()

        return ToolResult(
            success=True,
            data={"branch": branch},
        )
