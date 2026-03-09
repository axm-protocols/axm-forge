"""InitCheckTool — project conformity check as an AXMTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

__all__ = ["InitCheckTool"]


class InitCheckTool:
    """Check a project against the AXM gold standard.

    Registered as ``init_check`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_check"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Check a project against the AXM gold standard.

        Args:
            **kwargs: Keyword arguments.
                path: Path to project root.
                category: Optional category filter.

        Returns:
            ToolResult with check scores and details.
        """
        path: str = kwargs.get("path", ".")
        category: str | None = kwargs.get("category")
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_init.core.checker import CheckEngine, format_agent

            engine = CheckEngine(project_path, category=category)
            result = engine.run()
            return ToolResult(success=True, data=format_agent(result))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
