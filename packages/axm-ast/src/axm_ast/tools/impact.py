"""ImpactTool — change impact analysis."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypedDict, Unpack, cast

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.analyzer import (
    find_module_for_symbol,
    module_dotted_name,
    search_symbols,
)
from axm_ast.core.cache import get_package
from axm_ast.core.impact import ImpactResult
from axm_ast.core.impact_tests import validate_transitive_depth
from axm_ast.tools._base import log_and_fallback, safe_execute
from axm_ast.tools.impact_text import (
    render_impact_batch_text,
    render_impact_text,
)

logger = logging.getLogger(__name__)

_COMPACT_LINE_THRESHOLD = 5


class _ImpactOptions(TypedDict, total=False):
    """Opt-in analysis options forwarded to the core, present only when set.

    Omitting a disabled option (rather than passing its default) keeps the
    default delegation byte-for-byte identical to the legacy call, so a core
    or a test double that predates an option is never handed it.
    """

    test_filter: str | None
    include_module_importers: bool
    precise_callers: bool
    transitive_depth: int


def _impact_options(
    *,
    test_filter: str | None,
    include_module_importers: bool,
    precise_callers: bool,
    transitive_depth: int,
) -> _ImpactOptions:
    """Collect the enabled opt-ins, dropping every option left at its default."""
    opts: _ImpactOptions = {}
    if test_filter is not None:
        opts["test_filter"] = test_filter
    if include_module_importers:
        opts["include_module_importers"] = True
    if precise_callers:
        opts["precise_callers"] = True
    if transitive_depth:
        opts["transitive_depth"] = transitive_depth
    return opts


def _invalid_request(project_path: Path, transitive_depth: int) -> str | None:
    """Return the error message of an unusable request, ``None`` when valid."""
    if not project_path.is_dir():
        return f"Not a directory: {project_path}"
    try:
        validate_transitive_depth(transitive_depth)
    except ValueError as exc:
        return str(exc)
    return None


class _PreciseWorkspaceAnalyzer(Protocol):
    def __call__(  # noqa: PLR0913 - mirrors the workspace core option surface
        self,
        ws_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
        test_filter: str | None = None,
        transitive_depth: int = 0,
        precise_callers: bool = False,
    ) -> ImpactResult: ...


def _analyze_workspace(
    project_path: Path,
    symbol: str,
    exclude_tests: bool,
    opts: _ImpactOptions,
) -> ImpactResult:
    """Run the workspace core; raises ``ValueError`` outside a workspace.

    ``include_module_importers`` is not forwarded: the workspace core does not
    accept the reverse-import toggle yet (documented residual). A core that
    does not accept ``precise_callers`` is retried without it.
    """
    from axm_ast.core.impact import analyze_impact_workspace

    analyzer = cast("_PreciseWorkspaceAnalyzer", analyze_impact_workspace)
    test_filter = opts.get("test_filter")
    depth = opts.get("transitive_depth", 0)
    if opts.get("precise_callers"):
        try:
            return analyzer(
                project_path,
                symbol,
                exclude_tests=exclude_tests,
                test_filter=test_filter,
                transitive_depth=depth,
                precise_callers=True,
            )
        except TypeError as exc:
            if "unexpected keyword argument 'precise_callers'" not in str(exc):
                raise
    if depth:
        return analyze_impact_workspace(
            project_path,
            symbol,
            exclude_tests=exclude_tests,
            test_filter=test_filter,
            transitive_depth=depth,
        )
    return analyze_impact_workspace(
        project_path,
        symbol,
        exclude_tests=exclude_tests,
        test_filter=test_filter,
    )


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
    def execute(  # noqa: PLR0913 - opt-in toggles join the existing option surface
        self,
        *,
        path: str = ".",
        symbol: str | None = None,
        symbols: list[str] | None = None,
        exclude_tests: bool = False,
        detail: str | None = None,
        include_module_importers: bool = False,
        precise_callers: bool = False,
        transitive_depth: int = 0,
        **kwargs: object,
    ) -> ToolResult:
        """Analyze change impact for a symbol.

        Args:
            path: Path to package or workspace directory.
            symbol: Symbol name to analyze (required if symbols is not provided).
                Accepts ``func``, ``Class.method``, ``module.func`` and
                ``module.Class.method``. An ambiguous bare name expands to one
                report per module-qualified candidate; use one of those
                qualified names to replay a targeted query.
            symbols: Optional list of symbol names for batch inspection.
            exclude_tests: If True, exclude test files from impact analysis.
            detail: Output detail level. Use ``"compact"`` for a markdown
                table summary instead of the full JSON dict.
            include_module_importers: OPT-IN (default ``False``). When ``True``,
                forward the core reverse-import toggle so the result data carries
                a ``module_level_importers`` field listing modules that only
                ``import pkg.m`` the edited symbol's *module* (or a re-export
                shim of it) without referencing the symbol itself -- dependents a
                symbol-level traversal misses. Off (the default) the ToolResult
                data and text are byte-for-byte the legacy output (AC2).
                Best-effort: inert in workspace mode (the core
                ``analyze_impact_workspace`` does not yet accept the toggle -- a
                documented residual, single-package analysis is unaffected) and
                silently empty when the import graph is unavailable.
            precise_callers: OPT-IN (default ``False``). When ``True``,
                discard callers proven to import a distinct homonymous symbol.
                Ambiguous, unresolvable, or unreadable imports remain included
                (fail-open).
            transitive_depth: OPT-IN (default ``0``, off). When ``> 0``, the
                data adds ``transitive_test_file_paths``: the tests of the
                symbol AND of its in-package callers up to this many levels
                (a superset of ``test_file_paths``, which stays the direct
                references), plus ``transitive_callers`` (walked symbols) and
                ``transitive_truncated`` (visited-symbol budget hit). ``3`` is
                the measured sweet spot; at most ``10``. Off, data and text
                are the legacy output.
            **kwargs: Extra options. ``test_filter`` (``"none"``,
                ``"all"``, ``"related"``) controls test caller filtering.

        Returns:
            ToolResult with impact analysis.

        Note:
            Seeding (Volet B): the analysis seeds from *symbol* verbatim -- the
            tool never derives or proxies the seed. If a caller (the
            BUILD-briefing) hands in a derived/proxy symbol, that mis-seed lives
            on the caller side; it is a documented residual, not fixable here
            without forcing an axm-ast change.
        """
        if not symbol and not symbols:
            return ToolResult(success=False, error="symbol parameter is required")

        project_path = Path(path).resolve()
        invalid = _invalid_request(project_path, transitive_depth)
        if invalid is not None:
            return ToolResult(success=False, error=invalid)

        raw_filter = kwargs.get("test_filter")
        opts = _impact_options(
            test_filter=raw_filter if isinstance(raw_filter, str) else None,
            include_module_importers=include_module_importers,
            precise_callers=precise_callers,
            transitive_depth=transitive_depth,
        )

        try:
            if symbols is not None:
                return self._execute_batch(
                    project_path, symbols, exclude_tests, detail, opts
                )
            if symbol is None:
                return ToolResult(success=False, error="symbol parameter is required")
            return self._execute_symbol(
                project_path, symbol, exclude_tests, detail, opts
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))

    def _execute_symbol(
        self,
        project_path: Path,
        symbol: str,
        exclude_tests: bool,
        detail: str | None,
        opts: _ImpactOptions | None = None,
    ) -> ToolResult:
        opts = opts or {}
        candidates = self._qualified_candidates(project_path, symbol)
        if len(candidates) > 1:
            return self._execute_batch(
                project_path,
                sorted(candidates),
                exclude_tests,
                detail,
                opts,
                definition_files=candidates,
            )
        return self._execute_single(project_path, symbol, exclude_tests, detail, opts)

    @staticmethod
    def _qualified_candidates(project_path: Path, symbol: str) -> dict[str, str]:
        if "." in symbol:
            return {}
        try:
            pkg = get_package(project_path)
            candidates: dict[str, str] = {}
            for _, candidate in search_symbols(pkg, name=symbol):
                if candidate.name != symbol:
                    continue
                module = find_module_for_symbol(pkg, candidate)
                if module is None:
                    continue
                module_name = module.name or module_dotted_name(module.path, pkg.root)
                candidates[f"{module_name}.{symbol}"] = str(module.path)
            return candidates
        except Exception:  # noqa: BLE001 - ambiguity probing is best-effort
            return {}

    def _execute_batch(  # noqa: PLR0913 - opt-in toggles join the existing option surface
        self,
        project_path: Path,
        symbols: list[str],
        exclude_tests: bool,
        detail: str | None,
        opts: _ImpactOptions | None = None,
        *,
        definition_files: Mapping[str, str] | None = None,
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
        options: _ImpactOptions = opts or {}
        results: list[ImpactResult] = [
            self._analyze_single(
                project_path, sym, exclude_tests=exclude_tests, **options
            )
            for sym in symbols
        ]
        if definition_files is not None:
            for result in results:
                candidate_file = definition_files.get(result.get("symbol", ""))
                definition = result.get("definition")
                if candidate_file is not None and definition is not None:
                    definition_data = cast("dict[str, object]", definition)
                    definition_data["file"] = candidate_file
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
        opts: _ImpactOptions | None = None,
    ) -> ToolResult:
        """Run single-symbol impact analysis with optional compact output.

        In compact mode, returns formatted markdown via ``ToolResult.text``
        with an empty ``data`` dict. Otherwise returns the full report.
        """
        options: _ImpactOptions = opts or {}
        if detail != "compact":
            return self._analyze_single_result(
                project_path, symbol, exclude_tests=exclude_tests, **options
            )
        result = self._analyze_single(
            project_path, symbol, exclude_tests=exclude_tests, **options
        )
        return ToolResult(
            success=True,
            data={},
            text=format_impact_compact(result),
        )

    def _analyze_single_result(
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
        **opts: Unpack[_ImpactOptions],
    ) -> ToolResult:
        """Run single-symbol impact analysis and return a ToolResult."""
        result = self._analyze_single(
            project_path, symbol, exclude_tests=exclude_tests, **opts
        )
        if "error" in result:
            err = result.get("error", "")
            return ToolResult(
                success=False,
                error=err if isinstance(err, str) else str(err),
            )
        try:
            text: str | None = render_impact_text(result)
        except (KeyError, TypeError):
            text = None
        return ToolResult(
            success=True,
            data=cast("dict[str, object]", result),
            text=text,
        )

    def _analyze_single(  # noqa: PLR0913 - opt-in toggles join the option surface
        self,
        project_path: Path,
        symbol: str,
        *,
        exclude_tests: bool = False,
        test_filter: str | None = None,
        include_module_importers: bool = False,
        precise_callers: bool = False,
        transitive_depth: int = 0,
    ) -> ImpactResult:
        """Run impact analysis for a single symbol.

        The analysis seeds from *symbol* exactly as received (Volet B): the
        real edit-target, never a derived proxy. Workspace analysis is tried
        first; a non-workspace path falls back to the single-package core.

        Returns:
            Impact dict with ``score`` key on success,
            or ``{"symbol": name, "error": msg}`` on failure.
        """
        opts = _impact_options(
            test_filter=test_filter,
            include_module_importers=include_module_importers,
            precise_callers=precise_callers,
            transitive_depth=transitive_depth,
        )
        try:
            try:
                impact = _analyze_workspace(project_path, symbol, exclude_tests, opts)
            except ValueError:
                from axm_ast.core.impact import analyze_impact

                impact = analyze_impact(
                    project_path, symbol, exclude_tests=exclude_tests, **opts
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


def _caller_fields(c: Mapping[str, object]) -> tuple[str, int | None, str | None]:
    mod_raw = c.get("module", "?")
    mod = mod_raw if isinstance(mod_raw, str) else "?"
    line_raw = c.get("line")
    line = line_raw if isinstance(line_raw, int) else None
    name_raw = c.get("name")
    name = name_raw if isinstance(name_raw, str) else None
    return mod, line, name


def _format_prod_ref(mod: str, line: int | None, name: str | None) -> str:
    loc = f"{mod}:{line}" if line else mod
    return f"{name} ({loc})" if name else loc


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
    mod_suffix = symbol_module.rsplit(".", 1)[-1] if symbol_module else None

    for c in callers:
        mod, line, name = _caller_fields(c)
        file_name = mod.rsplit(".", 1)[-1]
        if "test" not in file_name:
            prod.append(_format_prod_ref(mod, line, name))
            continue
        bucket = direct if mod_suffix and mod_suffix in file_name else indirect
        bucket.setdefault(file_name, []).append(line or 0)
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


def _format_test_files_compact(test_files: list[str], limit: int = 5) -> str:
    """Format test file list with overflow indicator."""
    if not test_files:
        return "no test coverage"
    names = [f.rsplit("/", 1)[-1] for f in test_files]
    if len(names) <= limit:
        return ", ".join(names)
    shown = ", ".join(names[:limit])
    return f"{shown} (+{len(names) - limit} more)"


def _extract_callers(report: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Narrow ``report['callers']`` to a list of mappings."""
    callers_raw = report.get("callers", [])
    if not isinstance(callers_raw, list):
        return []
    return [c for c in callers_raw if isinstance(c, Mapping)]


def _format_caller_columns(
    callers: list[Mapping[str, object]],
    symbol_module: str | None,
) -> tuple[str, str, str]:
    """Return (prod, direct, indirect) column strings for a symbol row."""
    prod, direct, indirect = _classify_callers(callers, symbol_module)
    prod_str = ", ".join(prod) if prod else "\u2014"
    direct_str = _format_test_group(direct, cap=None) if direct else "\u2014"
    indirect_str = _format_test_group(indirect, cap=5) if indirect else "\u2014"
    return prod_str, direct_str, indirect_str


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
    sym_mod_raw = defn.get("module")
    symbol_module = sym_mod_raw if isinstance(sym_mod_raw, str) else None
    prod_str, direct_str, indirect_str = _format_caller_columns(
        _extract_callers(report),
        symbol_module,
    )
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
