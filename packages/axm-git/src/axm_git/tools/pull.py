"""GitPullTool — pull a remote branch into the local repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import not_a_repo_error, run_git, timeout_error_result
from axm_git.tools.pull_text import render_failure_text, render_text

__all__ = ["GitPullTool"]


class GitPullTool(AXMTool):
    """Pull a remote branch (default ``origin main``) into the local repo.

    Registered as ``git_pull`` via axm.tools entry point.
    """

    domain = "git"
    tags = frozenset({"pull", "sync", "remote"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_pull"

    def execute(
        self,
        *,
        branch: str = "main",
        remote: str = "origin",
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Pull *remote*/*branch* into the local repository.

        Args:
            branch: Remote branch to pull (default ``main``).
            remote: Remote name (default ``origin``).
            path: Repository path.

        Returns:
            ToolResult with ``pulled``, ``remote`` and ``branch`` on success.
        """
        resolved = Path(path).resolve()
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

            result = run_git(["pull", remote, branch], resolved)
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return ToolResult(
                    success=False,
                    error=f"git pull failed: {error}",
                    text=render_failure_text(error=error),
                )
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        data: dict[str, object] = {
            "pulled": True,
            "remote": remote,
            "branch": branch,
        }
        return ToolResult(success=True, data=data, text=render_text(data))
