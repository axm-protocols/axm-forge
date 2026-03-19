"""ImpactTool — change impact analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["ImpactTool"]


class ImpactTool(AXMTool):
    """Analyze blast radius of changing a symbol.

    Registered as ``ast_impact`` via axm.tools entry point.
    Workspace-aware: if path is a uv workspace root, analyzes
    impact across all member packages.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_impact"

    def execute(
        self,
        *,
        path: str = ".",
        symbol: str | None = None,
        symbols: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Analyze change impact for a symbol.

        Args:
            path: Path to package or workspace directory.
            symbol: Symbol name to analyze (required if symbols is not provided).
            symbols: Optional list of symbol names for batch inspection.

        Returns:
            ToolResult with impact analysis.
        """
        if not symbol and not symbols:
            return ToolResult(success=False, error="symbol parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            exclude_tests = bool(kwargs.get("exclude_tests", False))

            if symbols is not None:
                if not isinstance(symbols, list):
                    return ToolResult(
                        success=False, error="symbols parameter must be a list"
                    )
                results: list[dict[str, Any]] = []
                for sym in symbols:
                    results.append(
                        self._analyze_single(
                            project_path, sym, exclude_tests=exclude_tests
                        )
                    )
                return ToolResult(success=True, data={"symbols": results})

            assert symbol is not None  # already guarded above
            return self._analyze_single_result(
                project_path, symbol, exclude_tests=exclude_tests
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _analyze_single(
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
    ) -> dict[str, Any]:
        """Run impact analysis for a single symbol.

        Returns:
            Impact dict with ``severity`` key on success,
            or ``{"symbol": name, "error": msg}`` on failure.
        """
        try:
            from axm_ast.core.workspace import detect_workspace

            ws = detect_workspace(project_path)
            if ws is not None:
                from axm_ast.core.impact import analyze_impact_workspace

                impact = analyze_impact_workspace(
                    project_path, symbol, exclude_tests=exclude_tests
                )
            else:
                from axm_ast.core.impact import analyze_impact

                impact = analyze_impact(
                    project_path, symbol, exclude_tests=exclude_tests
                )

            impact["severity"] = impact.get("score", "UNKNOWN")
            if impact.get("definition") is None:
                return {"symbol": symbol, "error": f"Symbol '{symbol}' not found"}
            return impact
        except Exception as exc:
            return {"symbol": symbol, "error": str(exc)}

    def _analyze_single_result(
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
    ) -> ToolResult:
        """Run single-symbol impact analysis and return a ToolResult."""
        result = self._analyze_single(project_path, symbol, exclude_tests=exclude_tests)
        if "error" in result:
            return ToolResult(success=False, error=result["error"])
        return ToolResult(
            success=True,
            data=result,
            hint="Tip: Run affected tests, then ast_inspect on high-risk callers.",
        )
