"""Read-only delivered commit-range tool."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_git.core.range_diff import range_diff, resolve_revision

__all__ = ["RangeDiffTool"]


class RangeDiffTool(AXMTool):
    """Measure changed files and hunks for a commit range."""

    @property
    def name(self) -> str:
        return "git_range_diff"

    def execute(
        self, path: str = ".", base: str = "", head: str = "", **kwargs: object
    ) -> ToolResult:
        """Return a pinned commit-range footprint, without writing to the repo."""
        try:
            root = Path(path)
            base, head = resolve_revision(root, base), resolve_revision(root, head)
            files = range_diff(root, base, head)
        except (ValueError, OSError) as exc:
            return ToolResult(success=False, error=str(exc))
        data = {"base": base, "head": head, "files": [asdict(file) for file in files]}
        return ToolResult(success=True, data=data, text=str(data))
