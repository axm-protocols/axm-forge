"""MCP tool wrapper for doc impact analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["DocImpactTool"]


class DocImpactTool(AXMTool):
    """Analyze documentation impact for symbols.

    Registered as ``ast_doc_impact`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_doc_impact"

    def execute(
        self,
        *,
        path: str = ".",
        symbols: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Analyze doc impact for symbols.

        Args:
            path: Project root directory.
            symbols: Symbol names to analyze.
            **kwargs: Reserved for future use.

        Returns:
            ToolResult with doc impact data.
        """
        if not symbols:
            return ToolResult(success=False, error="symbols parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.doc_impact import analyze_doc_impact

            result = analyze_doc_impact(project_path, symbols)

            from axm_ast.tools.doc_impact_text import render_doc_impact_text

            text = render_doc_impact_text(result) if isinstance(result, dict) else None
            return ToolResult(success=True, data=result, text=text)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
