"""ImpactTool — change impact analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["ImpactTool", "format_impact_compact"]


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
        exclude_tests: bool = False,
        detail: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Analyze change impact for a symbol.

        Args:
            path: Path to package or workspace directory.
            symbol: Symbol name to analyze (required if symbols is not provided).
            symbols: Optional list of symbol names for batch inspection.
            exclude_tests: If True, exclude test files from impact analysis.
            detail: Output detail level. Use ``"compact"`` for a markdown
                table summary instead of the full JSON dict.

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

            if symbols is not None:
                return self._execute_batch(
                    project_path,
                    symbols,
                    exclude_tests,
                    detail,
                )

            assert symbol is not None  # already guarded above
            return self._execute_single(
                project_path,
                symbol,
                exclude_tests,
                detail,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _execute_batch(
        self,
        project_path: Path,
        symbols: list[str],
        exclude_tests: bool,
        detail: str | None,
    ) -> ToolResult:
        """Run batch impact analysis for multiple symbols."""
        if not isinstance(symbols, list):
            return ToolResult(success=False, error="symbols parameter must be a list")
        results: list[dict[str, Any]] = []
        for sym in symbols:
            results.append(
                self._analyze_single(project_path, sym, exclude_tests=exclude_tests)
            )
        if detail == "compact":
            from axm_ast.hooks.impact import _merge_impact_reports

            merged = _merge_impact_reports("\n".join(symbols), results)
            return ToolResult(
                success=True,
                data={"compact": format_impact_compact(merged)},
            )
        return ToolResult(success=True, data={"symbols": results})

    def _execute_single(
        self,
        project_path: Path,
        symbol: str,
        exclude_tests: bool,
        detail: str | None,
    ) -> ToolResult:
        """Run single-symbol impact analysis with optional compact output."""
        if detail == "compact":
            result = self._analyze_single(
                project_path,
                symbol,
                exclude_tests=exclude_tests,
            )
            return ToolResult(
                success=True,
                data={"compact": format_impact_compact(result)},
            )
        return self._analyze_single_result(
            project_path, symbol, exclude_tests=exclude_tests
        )

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


def format_impact_compact(impact: dict[str, Any]) -> str:
    """Format an impact analysis dict as a compact markdown table.

    Args:
        impact: Impact dict from ``_analyze_single`` or ``_merge_impact_reports``.

    Returns:
        Markdown string with symbol table and test-exposure footer.
    """
    lines: list[str] = []

    # Header
    lines.append("| Symbol | Module | Kind | Score | Callers |")
    lines.append("|--------|--------|------|-------|---------|")

    callers = impact.get("callers", [])
    caller_count = len(callers)
    score = impact.get("score") or impact.get("severity", "UNKNOWN")

    # Multi-symbol merged dict uses "definitions" list
    definitions = impact.get("definitions")
    if definitions:
        symbols = [
            s.strip() for s in impact.get("symbol", "").splitlines() if s.strip()
        ]
        for i, defn in enumerate(definitions):
            sym_name = symbols[i] if i < len(symbols) else "?"
            module = defn.get("module", "\u2014")
            kind = defn.get("kind", "\u2014")
            # Show score and caller count only on first row
            if i == 0:
                lines.append(
                    f"| {sym_name} | {module} | {kind} | {score} | {caller_count} |",
                )
            else:
                lines.append(f"| {sym_name} | {module} | {kind} | | |")
    else:
        # Single-symbol dict
        defn = impact.get("definition")
        sym_name = impact.get("symbol", "?")
        if defn is None or impact.get("error"):
            lines.append(
                f"| {sym_name} | \u2014 | \u2014 | {score} | not found |",
            )
        else:
            module = defn.get("module", "\u2014")
            kind = defn.get("kind", "\u2014")
            caller_str = str(caller_count) if caller_count else "\u2014"
            lines.append(
                f"| {sym_name} | {module} | {kind} | {score} | {caller_str} |",
            )

    # Test exposure footer
    test_files = impact.get("test_files", [])
    lines.append("")
    if test_files:
        lines.append(f"{len(test_files)} test files affected")
    else:
        lines.append("no test coverage")

    return "\n".join(lines)
