"""DocsTool — one-shot documentation tree dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["DocsTool"]


class DocsTool(AXMTool):
    """Dump README + mkdocs + docs tree in one call.

    Registered as ``ast_docs`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_docs"

    def execute(self, *, path: str = ".", **kwargs: Any) -> ToolResult:
        """Dump project documentation.

        Args:
            path: Project root directory.

        Returns:
            ToolResult with documentation data.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.docs import discover_docs, format_docs_json

            result = discover_docs(project_path)
            return ToolResult(success=True, data=format_docs_json(result))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
