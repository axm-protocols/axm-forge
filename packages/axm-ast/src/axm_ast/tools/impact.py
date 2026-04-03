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
            **kwargs: Extra options. ``test_filter`` (``"none"``,
                ``"all"``, ``"related"``) controls test caller filtering.

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

            test_filter: str | None = kwargs.get("test_filter")
            tf = {"test_filter": test_filter} if test_filter is not None else {}

            if symbols is not None:
                return self._execute_batch(
                    project_path,
                    symbols,
                    exclude_tests,
                    detail,
                    **tf,
                )

            assert symbol is not None  # already guarded above
            return self._execute_single(
                project_path,
                symbol,
                exclude_tests,
                detail,
                **tf,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _execute_batch(
        self,
        project_path: Path,
        symbols: list[str],
        exclude_tests: bool,
        detail: str | None,
        *,
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run batch impact analysis for multiple symbols."""
        if not isinstance(symbols, list):
            return ToolResult(success=False, error="symbols parameter must be a list")
        results: list[dict[str, Any]] = []
        for sym in symbols:
            tf = {"test_filter": test_filter} if test_filter is not None else {}
            results.append(
                self._analyze_single(
                    project_path,
                    sym,
                    exclude_tests=exclude_tests,
                    **tf,
                )
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
        *,
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run single-symbol impact analysis with optional compact output."""
        tf = {"test_filter": test_filter} if test_filter is not None else {}
        if detail == "compact":
            result = self._analyze_single(
                project_path,
                symbol,
                exclude_tests=exclude_tests,
                **tf,
            )
            return ToolResult(
                success=True,
                data={"compact": format_impact_compact(result)},
            )
        return self._analyze_single_result(
            project_path,
            symbol,
            exclude_tests=exclude_tests,
            **tf,
        )

    def _analyze_single(
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
        test_filter: str | None = None,
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
                    project_path,
                    symbol,
                    exclude_tests=exclude_tests,
                    test_filter=test_filter,
                )
            else:
                from axm_ast.core.impact import analyze_impact

                impact = analyze_impact(
                    project_path,
                    symbol,
                    exclude_tests=exclude_tests,
                    test_filter=test_filter,
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
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run single-symbol impact analysis and return a ToolResult."""
        tf = {"test_filter": test_filter} if test_filter is not None else {}
        result = self._analyze_single(
            project_path,
            symbol,
            exclude_tests=exclude_tests,
            **tf,
        )
        if "error" in result:
            return ToolResult(success=False, error=result["error"])
        return ToolResult(
            success=True,
            data=result,
            hint="Tip: Run affected tests, then ast_inspect on high-risk callers.",
        )


def _classify_callers(
    callers: list[dict[str, Any]],
    symbol_module: str | None,
) -> tuple[list[str], dict[str, list[int]], dict[str, list[int]]]:
    """Split callers into prod, direct-test, and indirect-test groups.

    Returns:
        Tuple of (prod_refs, direct_tests, indirect_tests) where
        prod_refs are ``module:line`` strings and test dicts map
        file name to sorted line numbers.
    """
    prod: list[str] = []
    direct: dict[str, list[int]] = {}
    indirect: dict[str, list[int]] = {}
    # Extract last component of symbol module for direct-test heuristic
    mod_suffix = symbol_module.rsplit(".", 1)[-1] if symbol_module else None

    for c in callers:
        mod = c.get("module", "?")
        line = c.get("line")
        # Extract file-level name (last dotted component)
        file_name = mod.rsplit(".", 1)[-1]
        if "test" in file_name:
            bucket = direct if mod_suffix and mod_suffix in file_name else indirect
            bucket.setdefault(file_name, []).append(line or 0)
        else:
            prod.append(f"{mod}:{line}" if line else mod)
    return prod, direct, indirect


def _format_test_group(tests: dict[str, list[int]], cap: int | None) -> str:
    """Format a group of test files with optional line cap.

    Args:
        tests: Mapping of test file name to line numbers.
        cap: Max lines to show per file, or None for no cap.
    """
    parts: list[str] = []
    for name, lines in tests.items():
        lines = sorted(lines)
        total = len(lines)
        if cap is not None and total > cap:
            shown = ",".join(str(ln) for ln in lines[:cap])
            parts.append(f"{name} (\u00d7{total}: {shown}\u2026)")
        elif total >= 5:
            shown = ",".join(str(ln) for ln in lines)
            parts.append(f"{name} (\u00d7{total}: {shown})")
        else:
            shown = ",".join(str(ln) for ln in lines)
            parts.append(f"{name} ({shown})")
    return ", ".join(parts)


def _format_callers_compact(
    callers: list[dict[str, Any]],
    symbol_module: str | None = None,
) -> str:
    """Format caller list with prod/test separation and grouping."""
    if not callers:
        return "\u2014"
    prod, direct, indirect = _classify_callers(callers, symbol_module)
    sections: list[str] = []
    if prod:
        sections.append(f"Prod: {', '.join(prod)}")
    if direct and indirect:
        sections.append(f"Direct tests: {_format_test_group(direct, cap=None)}")
        sections.append(f"Indirect tests: {_format_test_group(indirect, cap=5)}")
    elif direct:
        sections.append(f"Tests: {_format_test_group(direct, cap=None)}")
    elif indirect:
        sections.append(f"Tests: {_format_test_group(indirect, cap=5)}")
    return " | ".join(sections)


def _format_test_files_compact(test_files: list[str], limit: int = 5) -> str:
    """Format test file list with overflow indicator."""
    if not test_files:
        return "no test coverage"
    names = [f.rsplit("/", 1)[-1] for f in test_files]
    if len(names) <= limit:
        return ", ".join(names)
    shown = ", ".join(names[:limit])
    return f"{shown} (+{len(names) - limit} more)"


def _format_multi_symbol_rows(
    impact: dict[str, Any],
    definitions: list[Any],
    score: str,
    callers_str: str,
) -> list[str]:
    """Format rows for a multi-symbol merged impact dict."""
    lines: list[str] = []
    symbols = [s.strip() for s in impact.get("symbol", "").splitlines() if s.strip()]
    for i, defn in enumerate(definitions):
        sym_name = symbols[i] if i < len(symbols) else "?"
        mod_line = _defn_loc(defn)
        if i == 0:
            lines.append(f"| {sym_name} | {mod_line} | {score} | {callers_str} |")
        else:
            lines.append(f"| {sym_name} | {mod_line} | | |")
    return lines


def _format_single_symbol_row(
    impact: dict[str, Any],
    score: str,
    callers_str: str,
) -> list[str]:
    """Format row for a single-symbol impact dict."""
    defn = impact.get("definition")
    sym_name = impact.get("symbol", "?")
    if defn is None or impact.get("error"):
        return [f"| {sym_name} | \u2014 | {score} | not found |"]
    mod_line = _defn_loc(defn)
    return [f"| {sym_name} | {mod_line} | {score} | {callers_str} |"]


def format_impact_compact(impact: dict[str, Any]) -> str:
    """Format an impact analysis dict as a compact markdown table.

    Keeps actionable info (callers with module:line, test files)
    while dropping redundant fields (affected_modules, type_refs, etc.).

    Args:
        impact: Impact dict from ``_analyze_single`` or ``_merge_impact_reports``.

    Returns:
        Markdown string with symbol table, caller details, and test footer.
    """
    callers = impact.get("callers", [])
    score = impact.get("score") or impact.get("severity", "UNKNOWN")
    # Extract symbol module from definition for direct/indirect test classification
    defn = impact.get("definition")
    definitions = impact.get("definitions")
    if defn:
        symbol_module = defn.get("module")
    elif definitions:
        symbol_module = definitions[0].get("module")
    else:
        symbol_module = None
    callers_str = _format_callers_compact(callers, symbol_module=symbol_module)

    lines: list[str] = [
        "| Symbol | Module:Line | Score | Callers |",
        "|--------|------------|-------|---------|",
    ]

    definitions = impact.get("definitions")
    if definitions:
        lines.extend(_format_multi_symbol_rows(impact, definitions, score, callers_str))
    else:
        lines.extend(_format_single_symbol_row(impact, score, callers_str))

    test_files = impact.get("test_files", [])
    lines.append("")
    lines.append(f"Tests: {_format_test_files_compact(test_files)}")

    return "\n".join(lines)


def _defn_loc(defn: dict[str, Any]) -> str:
    """Format definition location as ``module:line``."""
    module = defn.get("module", "\u2014")
    line = defn.get("line")
    return f"{module}:{line}" if line else module
