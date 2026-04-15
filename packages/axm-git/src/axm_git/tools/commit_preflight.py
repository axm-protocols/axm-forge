"""GitPreflightTool — show working tree status for agent decision-making."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import find_git_root, not_a_repo_error, run_git

__all__ = ["GitPreflightTool"]

_MIN_STATUS_LINE_LEN = 4  # git porcelain format: "XY filename"


class GitPreflightTool(AXMTool):
    """Report working tree changes so the agent can plan commits.

    Registered as ``git_preflight`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_preflight"

    def execute(
        self,
        *,
        path: str = ".",
        diff_lines: int = 200,
        **kwargs: Any,
    ) -> ToolResult:
        """Show current working tree status and diff summary.

        Args:
            path: Project root (required).
            diff_lines: Max diff lines to include (default 200, 0 to
                disable).

        Returns:
            ToolResult with file list, statuses, diff stats, and diff content.
        """
        resolved = Path(path).resolve()
        max_diff_lines = diff_lines

        git_root = find_git_root(resolved)

        if git_root is not None:
            # Scope to subdirectory when inside a workspace
            rel = resolved.relative_to(git_root.resolve())
            pathspec = ["--", str(rel)] if str(rel) != "." else []
            cwd = git_root
        else:
            # Not a repo (or find_git_root failed) — fall through with
            # resolved so run_git triggers not_a_repo_error naturally.
            pathspec = []
            cwd = resolved

        # git status --porcelain [-- rel_path]
        status = run_git(["status", "--porcelain", *pathspec], cwd)
        if status.returncode != 0:
            return not_a_repo_error(status.stderr, resolved)

        files = []
        for line in status.stdout.splitlines():
            if len(line) < _MIN_STATUS_LINE_LEN:
                continue
            code = line[:2].strip()
            filepath = line[3:]
            files.append({"path": filepath, "status": code})

        # git diff --stat [-- rel_path] (only when dirty)
        diff_stat_out = ""
        if files:
            diff_stat = run_git(["diff", "--stat", *pathspec], cwd)
            diff_stat_out = diff_stat.stdout.strip()

        # git diff -U2 [-- rel_path] (reduced context, truncated to max_diff_lines)
        diff_content = ""
        diff_truncated = False
        if max_diff_lines > 0:
            diff_result = run_git(["diff", "-U2", *pathspec], cwd)
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
                "diff_stat": diff_stat_out,
                "diff": diff_content,
                "diff_truncated": diff_truncated,
                "clean": len(files) == 0,
            },
        )
