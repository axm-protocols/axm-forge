"""ImpactTool — change impact analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.services.tools.base import AXMTool, ToolResult

__all__ = ["ImpactTool"]


class ImpactTool(AXMTool):
    """Analyze blast radius of changing a symbol.

    Registered as ``ast_impact`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_impact"

    def execute(
        self, *, path: str = ".", symbol: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Analyze change impact for a symbol.

        Args:
            path: Path to package directory.
            symbol: Symbol name to analyze (required).

        Returns:
            ToolResult with impact analysis.
        """
        if not symbol:
            return ToolResult(success=False, error="symbol parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.impact import analyze_impact

            impact = analyze_impact(project_path, symbol)
            # Add "severity" alias for "score" for agent-friendly naming
            impact["severity"] = impact.get("score", "UNKNOWN")
            return ToolResult(success=True, data=impact)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
