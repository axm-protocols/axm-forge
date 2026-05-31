"""GitCloneTool — clone a remote or local git repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.runner import run_git, timeout_error_result

__all__ = ["GitCloneTool"]


class GitCloneTool(AXMTool):
    """Clone a git repository into a local directory.

    Registered as ``git_clone`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "git_clone"

    def execute(  # type: ignore[override]
        self,
        *,
        url: str,
        dest: str,
        path: str = ".",
        **kwargs: object,
    ) -> ToolResult:
        """Clone *url* into *dest* relative to *path*.

        Args:
            url: Repository URL or local path to clone from.
            dest: Destination directory name (relative to *path*).
            path: Parent directory in which to create the clone
                (default: current working directory).

        Returns:
            ToolResult with url, dest, absolute clone path, and
            ``cloned: True`` on success.
        """
        cwd = Path(path).resolve()

        try:
            # Clone can be slow over a network — use timeout=None so large
            # repos are not killed mid-transfer.  Local clones are fast;
            # callers that need a hard limit can wrap this tool themselves.
            result = run_git(["clone", url, dest], cwd, timeout=None)
        except subprocess.TimeoutExpired as exc:
            return timeout_error_result(exc)

        if result.returncode != 0:
            return ToolResult(success=False, error=result.stderr.strip())

        return ToolResult(
            success=True,
            data={
                "url": url,
                "dest": dest,
                "path": str(cwd / dest),
                "cloned": True,
            },
        )
