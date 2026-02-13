"""GitPreflightTool — show working tree status for agent decision-making."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import run_git

__all__ = ["GitPreflightTool"]


class GitPreflightTool(AXMTool):
    """Report working tree changes so the agent can plan commits.

    Registered as ``git_preflight`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_preflight"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Show current working tree status and diff summary.

        Args:
            **kwargs: Keyword arguments.
                path: Project root (required).

        Returns:
            ToolResult with file list, statuses, and diff stats.
        """
        path = Path(kwargs.get("path", ".")).resolve()

        # git status --porcelain
        status = run_git(["status", "--porcelain"], path)
        if status.returncode != 0:
            return ToolResult(
                success=False,
                error=f"git status failed: {status.stderr.strip()}",
            )

        files = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code = line[:2].strip()
            filepath = line[3:]
            files.append({"path": filepath, "status": code})

        # git diff --stat
        diff_stat = run_git(["diff", "--stat"], path)

        return ToolResult(
            success=True,
            data={
                "files": files,
                "file_count": len(files),
                "diff_stat": diff_stat.stdout.strip(),
                "clean": len(files) == 0,
            },
        )
