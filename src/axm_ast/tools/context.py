"""ContextTool — one-shot project context dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.services.tools.base import AXMTool, ToolResult

__all__ = ["ContextTool"]


class ContextTool(AXMTool):
    """One-shot project context: stack, patterns, module ranking.

    Registered as ``ast_context`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_context"

    def execute(self, *, path: str = ".", **kwargs: Any) -> ToolResult:
        """Dump complete project context for AI agents.

        Args:
            path: Path to package directory.

        Returns:
            ToolResult with project context data.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.context import build_context, format_context_json

            ctx = build_context(project_path)
            return ToolResult(success=True, data=format_context_json(ctx))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
