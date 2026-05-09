"""ImpactHook & DocImpactHook — blast-radius and doc-impact analysis.

Protocol hooks registered via ``axm.hooks`` entry points:

- ``ast:impact`` → ``ImpactHook`` — calls ``analyze_impact``, returns
  the complete impact report as ``HookResult`` metadata.  Supports
  newline-separated symbol lists with max-score merge semantics.

- ``ast:doc-impact`` → ``DocImpactHook`` — calls ``analyze_doc_impact``,
  returns ``doc_refs`` as ``HookResult`` metadata.  Supports
  newline-separated symbol lists.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from axm.hooks.base import HookResult

from axm_ast.core.impact import ImpactResult

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import NotRequired


class EnrichedImpactResult(ImpactResult, total=False):
    """ImpactResult enriched with witness-friendly aliases.

    Adds ``test_paths`` (alias for ``test_files``) and ``packages``
    (space-separated dirs from ``cross_package_impact``) so that
    witness templates can extract them directly.
    """

    test_paths: NotRequired[list[str]]
    packages: NotRequired[str]


logger = logging.getLogger(__name__)

__all__ = ["DocImpactHook", "ImpactHook"]

_SCORE_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Single source of truth for merge fields.
# Each entry: (key, dedup) — dedup=True means sorted(set(...)) after merge.
_MERGE_FIELDS: tuple[tuple[str, bool], ...] = (
    ("callers", False),
    ("type_refs", False),
    ("reexports", False),
    ("affected_modules", True),
    ("test_files", True),
    ("git_coupled", False),
)


def _merge_impact_reports(
    symbol: str,
    reports: list[ImpactResult],
) -> dict[str, object]:
    """Merge multiple impact reports into a single result.

    Uses max-score semantics and deduplicates ``affected_modules``
    and ``test_files``.

    Args:
        symbol: Original (possibly multi-line) symbol string.
        reports: List of individual impact analysis dicts.

    Returns:
        Single merged impact dict (untyped — has a ``definitions`` list
        that does not exist in :class:`ImpactResult`).
    """
    merged: dict[str, object] = {
        "symbol": symbol,
        "definitions": [],
        "score": "LOW",
    }
    for key, _dedup in _MERGE_FIELDS:
        merged[key] = []

    for report in reports:
        defn = report.get("definition")
        if defn:
            cast("list[object]", merged["definitions"]).append(defn)
        for key, _dedup in _MERGE_FIELDS:
            cast("list[object]", merged[key]).extend(
                cast("list[object]", report.get(key, []))
            )
        rpt_score = report.get("score", "LOW")
        if _SCORE_ORDER.get(rpt_score, 0) > _SCORE_ORDER.get(
            cast("str", merged["score"]), 0
        ):
            merged["score"] = rpt_score

    # Deduplicate sortable lists.
    for key, dedup in _MERGE_FIELDS:
        if dedup:
            merged[key] = sorted(set(cast("list[str]", merged[key])))

    return merged


def _parse_impact_params(
    context: dict[str, object],
    params: dict[str, object],
) -> tuple[Path, str, list[str], bool, str | None] | HookResult:
    """Parse and validate ImpactHook parameters.

    Returns:
        ``(working_dir, symbol, symbols, exclude_tests, detail)`` on success,
        or a ``HookResult`` on validation failure.
    """
    symbol = params.get("symbol")
    if not symbol or not isinstance(symbol, str):
        return HookResult.fail("Missing required param 'symbol'")

    raw_path = params.get("path") or context.get("working_dir", ".")
    if not isinstance(raw_path, (str, Path)):
        return HookResult.fail(
            f"path must be str or Path, got {type(raw_path).__name__}"
        )
    working_dir = Path(raw_path)
    if not working_dir.is_dir():
        return HookResult.fail(f"working_dir not a directory: {working_dir}")

    exclude_tests = bool(params.get("exclude_tests", False))
    raw_detail = params.get("detail")
    detail: str | None
    if raw_detail is None or isinstance(raw_detail, str):
        detail = raw_detail
    else:
        return HookResult.fail(
            f"detail must be str or None, got {type(raw_detail).__name__}"
        )
    symbols = [s.strip() for s in symbol.splitlines() if s.strip()]

    return working_dir, symbol, symbols, exclude_tests, detail


def _enrich_report(report: ImpactResult) -> EnrichedImpactResult:
    """Add witness-friendly aliases to a structured impact report.

    Adds ``test_paths`` (alias for ``test_files``) and ``packages``
    (space-separated dirs from ``cross_package_impact``) so that
    witness templates can extract them directly.
    """
    enriched = cast("EnrichedImpactResult", report)
    enriched["test_paths"] = list(report.get("test_files", []))

    cross = report.get("cross_package_impact", [])
    if isinstance(cross, list):
        dirs: list[str] = [
            entry.get("path", "") if isinstance(entry, dict) else str(entry)
            for entry in cross
        ]
        enriched["packages"] = " ".join(d for d in dirs if d)
    else:
        enriched["packages"] = ""
    return enriched


@dataclass
class ImpactHook:
    """Run impact analysis on one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is analyzed separately and results are
    merged (max score, concatenated lists, deduplicated modules/tests).
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Must include ``symbol`` (name to analyze).
                Optional ``path`` (overrides ``working_dir`` from context).
                Optional ``detail`` (``"compact"`` for short format).

        Returns:
            HookResult with ``impact`` dict and ``packages`` in metadata.
            ``text`` is populated with a human-readable render via
            ``render_impact_text`` (single symbol) or
            ``render_impact_batch_text`` (multiple symbols).
            In compact mode, ``text`` is *None* and ``impact`` holds
            a pre-formatted string instead.
        """
        parsed = _parse_impact_params(context, params)
        if isinstance(parsed, HookResult):
            return parsed
        working_dir, symbol, symbols, exclude_tests, detail = parsed

        try:
            from axm_ast.core.impact import analyze_impact
            from axm_ast.tools.impact import (
                render_impact_batch_text,
                render_impact_text,
            )

            text: str | None = None
            if len(symbols) == 1:
                single_report: ImpactResult = analyze_impact(
                    working_dir,
                    symbols[0],
                    project_root=working_dir.parent,
                    exclude_tests=exclude_tests,
                )
            else:

                def _analyze(sym: str) -> ImpactResult:
                    return analyze_impact(
                        working_dir,
                        sym,
                        project_root=working_dir.parent,
                        exclude_tests=exclude_tests,
                    )

                with ThreadPoolExecutor(max_workers=min(len(symbols), 4)) as pool:
                    reports: list[ImpactResult] = list(pool.map(_analyze, symbols))

                if detail == "compact":
                    from axm_ast.tools.impact import format_impact_compact

                    return HookResult.ok(
                        impact=format_impact_compact(
                            cast("list[Mapping[str, object]]", reports)
                        ),
                    )
                text = render_impact_batch_text(reports)
                merged = _merge_impact_reports(symbol, reports)
                # The merged dict is a superset of ImpactResult (adds
                # ``definitions``), but downstream consumers only read
                # ImpactResult-shaped fields plus the enrichment additions.
                single_report = cast("ImpactResult", merged)

            if detail == "compact":
                from axm_ast.tools.impact import format_impact_compact

                return HookResult.ok(
                    impact=format_impact_compact(
                        cast("Mapping[str, object]", single_report)
                    )
                )

            if len(symbols) == 1:
                text = render_impact_text(single_report)

            enriched = _enrich_report(single_report)
            return HookResult(
                success=True,
                metadata={
                    "impact": enriched,
                    "packages": enriched.get("packages", ""),
                },
                text=text,
            )
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Impact analysis failed: {exc}")


class DocImpactHook:
    """Run doc impact analysis on one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is treated as a separate symbol.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Must include ``symbol`` (name to analyze).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with full report (``doc_refs``, ``undocumented``,
                ``stale_signatures``) in metadata on success.
        """
        symbol = params.get("symbol")
        if not symbol or not isinstance(symbol, str):
            return HookResult.fail("Missing required param 'symbol'")

        raw_path = params.get("path") or context.get("working_dir", ".")
        if not isinstance(raw_path, (str, Path)):
            return HookResult.fail(
                f"path must be str or Path, got {type(raw_path).__name__}"
            )
        working_dir = Path(raw_path)
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            from axm_ast.core.doc_impact import analyze_doc_impact

            symbols = [s.strip() for s in symbol.splitlines() if s.strip()]
            report = analyze_doc_impact(working_dir, symbols)
            return HookResult.ok(**cast("dict[str, object]", report))
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Doc impact analysis failed: {exc}")
