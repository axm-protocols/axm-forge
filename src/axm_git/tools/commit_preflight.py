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
                diff_lines: Max diff lines to include (default 200, 0 to
                    disable).

        Returns:
            ToolResult with file list, statuses, diff stats, and diff content.
        """
        path = Path(kwargs.get("path", ".")).resolve()
        max_diff_lines: int = int(kwargs.get("diff_lines", 200))

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

        # git diff -U2 (reduced context, truncated to max_diff_lines)
        diff_content = ""
        diff_truncated = False
        if max_diff_lines > 0:
            diff_result = run_git(["diff", "-U2"], path)
            lines = diff_result.stdout.splitlines()
            if len(lines) > max_diff_lines:
                diff_content = "\n".join(lines[:max_diff_lines])
                diff_truncated = True
            else:
                diff_content = diff_result.stdout.strip()

        return ToolResult(
            success=True,
            data={
                "files": files,
                "file_count": len(files),
                "diff_stat": diff_stat.stdout.strip(),
                "diff": diff_content,
                "diff_truncated": diff_truncated,
                "clean": len(files) == 0,
            },
        )
