"""ImpactTool — change impact analysis."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.impact import ImpactResult
from axm_ast.tools._base import log_and_fallback, safe_execute
from axm_ast.tools.impact_text import (
    render_impact_batch_text,
    render_impact_text,
)

logger = logging.getLogger(__name__)

_COMPACT_LINE_THRESHOLD = 5

__all__ = [
    "ImpactTool",
    "format_impact_compact",
    "format_impact_compact_multi",
    "render_impact_batch_text",
    "render_impact_text",
]


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

    @safe_execute
    def execute(
        self,
        *,
        path: str = ".",
        symbol: str | None = None,
        symbols: list[str] | None = None,
        exclude_tests: bool = False,
        detail: str | None = None,
        **kwargs: object,
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

        project_path = Path(path).resolve()
        if not project_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {project_path}")

        raw_filter = kwargs.get("test_filter")
        test_filter: str | None = raw_filter if isinstance(raw_filter, str) else None
        tf: dict[str, str | None] = (
            {"test_filter": test_filter} if test_filter is not None else {}
        )

        if symbols is not None:
            return self._execute_batch(
                project_path,
                symbols,
                exclude_tests,
                detail,
                **tf,
            )

        if symbol is None:
            return ToolResult(success=False, error="symbol parameter is required")
        return self._execute_single(
            project_path,
            symbol,
            exclude_tests,
            detail,
            **tf,
        )

    def _execute_batch(
        self,
        project_path: Path,
        symbols: list[str],
        exclude_tests: bool,
        detail: str | None,
        *,
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run batch impact analysis for multiple symbols.

        In compact mode, returns formatted markdown via ``ToolResult.text``
        with an empty ``data`` dict. In full mode, returns per-symbol dicts
        under ``data["symbols"]``.
        """
        if not isinstance(symbols, list):
            return ToolResult(success=False, error="symbols parameter must be a list")
        if not symbols:
            return ToolResult(success=False, error="symbols list must not be empty")
        results: list[ImpactResult] = []
        for sym in symbols:
            tf: dict[str, str | None] = (
                {"test_filter": test_filter} if test_filter is not None else {}
            )
            results.append(
                self._analyze_single(
                    project_path,
                    sym,
                    exclude_tests=exclude_tests,
                    **tf,
                )
            )
        if detail == "compact":
            return ToolResult(
                success=True,
                data={},
                text=format_impact_compact(cast("list[Mapping[str, object]]", results)),
            )
        text = self._render_batch_text(results)
        return ToolResult(
            success=True,
            data={"symbols": cast("list[dict[str, object]]", results)},
            text=text,
        )

    @staticmethod
    def _render_batch_text(results: list[ImpactResult]) -> str | None:
        """Render batch text from results, returning *None* on failure."""
        try:
            if any("score" in r or "callers" in r for r in results):
                return render_impact_batch_text([dict(r) for r in results])
        except (KeyError, TypeError):
            pass
        return None

    def _execute_single(
        self,
        project_path: Path,
        symbol: str,
        exclude_tests: bool,
        detail: str | None,
        *,
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run single-symbol impact analysis with optional compact output.

        In compact mode, returns formatted markdown via ``ToolResult.text``
        with an empty ``data`` dict. Otherwise delegates to
        ``_analyze_single_result``.
        """
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
                data={},
                text=format_impact_compact(result),
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
    ) -> ImpactResult:
        """Run impact analysis for a single symbol.

        Returns:
            Impact dict with ``score`` key on success,
            or ``{"symbol": name, "error": msg}`` on failure.
        """
        try:
            try:
                from axm_ast.core.impact import analyze_impact_workspace

                impact = analyze_impact_workspace(
                    project_path,
                    symbol,
                    exclude_tests=exclude_tests,
                    test_filter=test_filter,
                )
            except ValueError:
                from axm_ast.core.impact import analyze_impact

                impact = analyze_impact(
                    project_path,
                    symbol,
                    exclude_tests=exclude_tests,
                    test_filter=test_filter,
                )

            if impact.get("definition") is None:
                return cast(
                    "ImpactResult",
                    {"symbol": symbol, "error": f"Symbol '{symbol}' not found"},
                )
            return impact
        except Exception as exc:  # noqa: BLE001 — final boundary
            return cast(
                "ImpactResult",
                log_and_fallback(logger, exc, {"symbol": symbol, "error": str(exc)}),
            )

    def _analyze_single_result(
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
        test_filter: str | None = None,
    ) -> ToolResult:
        """Run single-symbol impact analysis and return a ToolResult."""
        tf: dict[str, str | None] = (
            {"test_filter": test_filter} if test_filter is not None else {}
        )
        result = self._analyze_single(
            project_path,
            symbol,
            exclude_tests=exclude_tests,
            **tf,
        )
        if "error" in result:
            err = result.get("error", "")
            return ToolResult(
                success=False,
                error=err if isinstance(err, str) else str(err),
            )
        try:
            text: str | None = render_impact_text(dict(result))
        except (KeyError, TypeError):
            text = None
        return ToolResult(
            success=True,
            data=cast("dict[str, object]", result),
            text=text,
        )


def _classify_callers(
    callers: list[Mapping[str, object]],
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
        mod_raw = c.get("module", "?")
        mod = mod_raw if isinstance(mod_raw, str) else "?"
        line_raw = c.get("line")
        line = line_raw if isinstance(line_raw, int) else None
        # Extract file-level name (last dotted component)
        file_name = mod.rsplit(".", 1)[-1]
        if "test" in file_name:
            bucket = direct if mod_suffix and mod_suffix in file_name else indirect
            bucket.setdefault(file_name, []).append(line or 0)
        else:
            name_raw = c.get("name")
            name = name_raw if isinstance(name_raw, str) else None
            loc = f"{mod}:{line}" if line else mod
            prod.append(f"{name} ({loc})" if name else loc)
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
        elif total >= _COMPACT_LINE_THRESHOLD:
            shown = ",".join(str(ln) for ln in lines)
            parts.append(f"{name} (\u00d7{total}: {shown})")
        else:
            shown = ",".join(str(ln) for ln in lines)
            parts.append(f"{name} ({shown})")
    return ", ".join(parts)


def _format_callers_compact(
    callers: list[Mapping[str, object]],
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


def _format_symbol_row(
    report: Mapping[str, object],
    score: str,
) -> str:
    """Format a single symbol as one table row with per-symbol callers."""
    sym_name_raw = report.get("symbol", "?")
    sym_name = sym_name_raw if isinstance(sym_name_raw, str) else "?"
    defn = report.get("definition")
    if not isinstance(defn, Mapping) or report.get("error"):
        return f"| {sym_name} | \u2014 | {score} | not found | | |"
    mod_line = _defn_loc(defn)
    callers_raw = report.get("callers", [])
    callers: list[Mapping[str, object]] = (
        [c for c in callers_raw if isinstance(c, Mapping)]
        if isinstance(callers_raw, list)
        else []
    )
    sym_mod_raw = defn.get("module")
    symbol_module = sym_mod_raw if isinstance(sym_mod_raw, str) else None
    prod, direct, indirect = _classify_callers(callers, symbol_module)
    prod_str = ", ".join(prod) if prod else "\u2014"
    direct_str = _format_test_group(direct, cap=None) if direct else "\u2014"
    indirect_str = _format_test_group(indirect, cap=5) if indirect else "\u2014"
    return (
        f"| {sym_name} | {mod_line} | {score} "
        f"| {prod_str} | {direct_str} | {indirect_str} |"
    )


def format_impact_compact_multi(
    reports: list[Mapping[str, object]],
    score: str,
) -> str:
    """Format multiple impact reports as a compact table with per-symbol callers.

    Each symbol gets its own row with its own Prod / Direct tests / Indirect
    tests columns.  Each row displays the per-symbol score from the report.

    Args:
        reports: Individual per-symbol impact dicts.
        score: Kept for backward compatibility (not used for row display).

    Returns:
        Markdown table string.
    """
    lines: list[str] = [
        "| Symbol | Location | Score | Prod | Direct tests | Indirect tests |",
        "|---|---|---|---|---|---|",
    ]
    for report in reports:
        row_score_raw = report.get("score", "LOW")
        row_score = row_score_raw if isinstance(row_score_raw, str) else "LOW"
        lines.append(_format_symbol_row(report, row_score))

    # Aggregate test_files across all reports
    seen: set[str] = set()
    all_test_files: list[str] = []
    for report in reports:
        report_tfs = report.get("test_files", [])
        if not isinstance(report_tfs, list):
            continue
        for tf in report_tfs:
            if isinstance(tf, str) and tf not in seen:
                seen.add(tf)
                all_test_files.append(tf)
    lines.append("")
    lines.append(f"Tests: {_format_test_files_compact(all_test_files)}")
    return "\n".join(lines)


def format_impact_compact(
    impact: Mapping[str, object] | list[Mapping[str, object]],
) -> str:
    """Format impact analysis as a compact markdown table.

    Accepts either a single impact dict or a list of per-symbol reports.
    When given a list, each symbol gets its own row with per-symbol callers.

    Args:
        impact: Single impact dict or list of per-symbol impact dicts.

    Returns:
        Markdown string with symbol table, caller details, and test footer.
    """
    if isinstance(impact, list):
        score = _max_score(impact)
        return format_impact_compact_multi(impact, score)

    # Single-report dict path
    score_raw = impact.get("score", "UNKNOWN")
    score = score_raw if isinstance(score_raw, str) else "UNKNOWN"
    return format_impact_compact_multi([impact], score)


def _max_score(reports: list[Mapping[str, object]]) -> str:
    """Compute the max score across a list of impact reports."""
    score_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    best = "LOW"
    for report in reports:
        rpt_score_raw = report.get("score", "LOW")
        rpt_score = rpt_score_raw if isinstance(rpt_score_raw, str) else "LOW"
        if score_order.get(rpt_score, 0) > score_order.get(best, 0):
            best = rpt_score
    return best


def _defn_loc(defn: Mapping[str, object]) -> str:
    """Format definition location as ``module:line``."""
    module_raw = defn.get("module", "\u2014")
    module = module_raw if isinstance(module_raw, str) else "\u2014"
    line_raw = defn.get("line")
    line = line_raw if isinstance(line_raw, int) else None
    return f"{module}:{line}" if line else module
