"""ImpactTool — change impact analysis."""

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

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
        """Run batch impact analysis for multiple symbols.

        In compact mode, returns formatted markdown via ``ToolResult.text``
        with an empty ``data`` dict. In full mode, returns per-symbol dicts
        under ``data["symbols"]``.
        """
        if not isinstance(symbols, list):
            return ToolResult(success=False, error="symbols parameter must be a list")
        if not symbols:
            return ToolResult(success=False, error="symbols list must not be empty")
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
            return ToolResult(
                success=True,
                data={},
                text=format_impact_compact(results),
            )
        text = self._render_batch_text(results)
        return ToolResult(success=True, data={"symbols": results}, text=text)

    @staticmethod
    def _render_batch_text(results: list[dict[str, Any]]) -> str | None:
        """Render batch text from results, returning *None* on failure."""
        try:
            if any("score" in r or "callers" in r for r in results):
                return render_impact_batch_text(results)
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
    ) -> dict[str, Any]:
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
        try:
            text = render_impact_text(result)
        except (KeyError, TypeError):
            text = None
        return ToolResult(
            success=True,
            data=result,
            text=text,
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
            name = c.get("name")
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


def _format_symbol_row(
    report: dict[str, Any],
    score: str,
) -> str:
    """Format a single symbol as one table row with per-symbol callers."""
    sym_name = report.get("symbol", "?")
    defn = report.get("definition")
    if defn is None or report.get("error"):
        return f"| {sym_name} | \u2014 | {score} | not found | | |"
    mod_line = _defn_loc(defn)
    callers = report.get("callers", [])
    symbol_module = defn.get("module")
    prod, direct, indirect = _classify_callers(callers, symbol_module)
    prod_str = ", ".join(prod) if prod else "\u2014"
    direct_str = _format_test_group(direct, cap=None) if direct else "\u2014"
    indirect_str = _format_test_group(indirect, cap=5) if indirect else "\u2014"
    return (
        f"| {sym_name} | {mod_line} | {score} "
        f"| {prod_str} | {direct_str} | {indirect_str} |"
    )


def format_impact_compact_multi(
    reports: list[dict[str, Any]],
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
        row_score = report.get("score", "LOW")
        lines.append(_format_symbol_row(report, row_score))

    # Aggregate test_files across all reports
    seen: set[str] = set()
    all_test_files: list[str] = []
    for report in reports:
        for tf in report.get("test_files", []):
            if tf not in seen:
                seen.add(tf)
                all_test_files.append(tf)
    lines.append("")
    lines.append(f"Tests: {_format_test_files_compact(all_test_files)}")
    return "\n".join(lines)


def format_impact_compact(
    impact: dict[str, Any] | list[dict[str, Any]],
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
    score = impact.get("score", "UNKNOWN")
    return format_impact_compact_multi([impact], score)


def _max_score(reports: list[dict[str, Any]]) -> str:
    """Compute the max score across a list of impact reports."""
    score_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    best = "LOW"
    for report in reports:
        rpt_score = report.get("score", "LOW")
        if score_order.get(rpt_score, 0) > score_order.get(best, 0):
            best = rpt_score
    return best


def _defn_loc(defn: dict[str, Any]) -> str:
    """Format definition location as ``module:line``."""
    module = defn.get("module", "\u2014")
    line = defn.get("line")
    return f"{module}:{line}" if line else module


# ─── Text rendering ─────────────────────────────────────────────────────────


def _render_definition_section(defn: dict[str, Any]) -> list[str]:
    """Render the definition section lines."""
    kind = defn.get("kind", "")
    mod = defn.get("module", "?")
    ln = defn.get("line", "?")
    lines = [f"Def: {mod}:{ln} ({kind})"]
    sig = defn.get("signature")
    if sig:
        lines.append(sig)
    return lines


def _render_callers_section(callers: list[dict[str, Any]]) -> list[str]:
    """Render the callers section lines."""
    if not callers:
        return ["Callers: none"]
    parts = []
    for c in callers:
        name = c.get("name", "?")
        cmod = c.get("module", "?")
        cline = c.get("line")
        loc = f"{cmod}:{cline}" if cline else cmod
        parts.append(f"{name} ({loc})")
    return [f"Callers: {', '.join(parts)}"]


def _render_tests_section(test_files: list[str]) -> list[str]:
    """Render the tests section lines."""
    if not test_files:
        return ["Tests: none"]
    names = [f.rsplit("/", 1)[-1] for f in test_files]
    return [f"Tests: {', '.join(names)}"]


def _render_git_coupled_section(git_coupled: list[str]) -> list[str]:
    """Render the git-coupled section lines."""
    if not git_coupled:
        return []
    names = [f.rsplit("/", 1)[-1] for f in git_coupled]
    return [f"Git-coupled: {', '.join(names)}"]


def _render_cross_package_section(cross: list[Any]) -> list[str]:
    """Render the cross-package impact section lines."""
    if not cross:
        return []
    pkgs = ", ".join(
        str(c.get("package", c.get("module", "?"))) if isinstance(c, dict) else str(c)
        for c in cross
    )
    return [f"Cross-package: {pkgs}"]


def _render_impact_single(report: dict[str, Any]) -> str:
    """Render a single impact report dict as text."""
    symbol = report.get("symbol", "?")

    if "error" in report:
        return f"ast_impact | {symbol} | error\n{report['error']}"

    score = report.get("score", "UNKNOWN")
    lines: list[str] = [f"ast_impact | {symbol} | {score}"]

    defn = report.get("definition")
    if defn:
        lines.extend(_render_definition_section(defn))

    lines.extend(_render_callers_section(report.get("callers", [])))

    affected = report.get("affected_modules", [])
    if affected:
        lines.append(f"Affected: {', '.join(affected)}")

    lines.extend(_render_tests_section(report.get("test_files", [])))
    lines.extend(_render_git_coupled_section(report.get("git_coupled", [])))
    lines.extend(_render_cross_package_section(report.get("cross_package_impact", [])))

    return "\n".join(lines)


def render_impact_text(report: dict[str, Any]) -> str:
    """Render a single impact report as human-readable text."""
    try:
        return _render_impact_single(report)
    except (KeyError, TypeError, AttributeError):
        symbol = report.get("symbol", "?") if isinstance(report, dict) else "?"
        return f"ast_impact | {symbol} | render error"


def render_impact_batch_text(reports: list[dict[str, Any]]) -> str:
    """Render multiple impact reports as human-readable text."""
    if not reports:
        return ""

    try:
        score_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        best = "LOW"
        for r in reports:
            s = r.get("score", "LOW")
            if score_order.get(s, 0) > score_order.get(best, 0):
                best = s
        header = f"ast_impact | {len(reports)} symbols | max={best}"
        sections: list[str] = [header]
        for r in reports:
            symbol = r.get("symbol", "?")
            score = r.get("score", "UNKNOWN")
            section_header = f"## {symbol} | {score}"
            body = _render_impact_single(r)
            body_lines = body.split("\n")[1:]
            sections.append(section_header + "\n" + "\n".join(body_lines))
        return "\n\n".join(sections)
    except (KeyError, TypeError, AttributeError):
        return ""


# ─── Virtual submodule for ``from axm_ast.tools.impact_text import …`` ───────

_impact_text_mod = types.ModuleType("axm_ast.tools.impact_text")
_impact_text_mod.render_impact_text = render_impact_text  # type: ignore[attr-defined]
_impact_text_mod.render_impact_batch_text = render_impact_batch_text  # type: ignore[attr-defined]
_impact_text_mod.__all__ = ["render_impact_batch_text", "render_impact_text"]  # type: ignore[attr-defined]
sys.modules["axm_ast.tools.impact_text"] = _impact_text_mod
