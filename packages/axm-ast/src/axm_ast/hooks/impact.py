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
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["ImpactHook", "_merge_impact_reports"]

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
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge multiple impact reports into a single result.

    Uses max-score semantics and deduplicates ``affected_modules``
    and ``test_files``.

    Args:
        symbol: Original (possibly multi-line) symbol string.
        reports: List of individual impact analysis dicts.

    Returns:
        Single merged impact dict.
    """
    merged: dict[str, Any] = {
        "symbol": symbol,
        "definitions": [],
        "score": "LOW",
    }
    for key, _dedup in _MERGE_FIELDS:
        merged[key] = []

    for report in reports:
        defn = report.get("definition")
        if defn:
            merged["definitions"].append(defn)
        for key, _dedup in _MERGE_FIELDS:
            merged[key].extend(report.get(key, []))
        rpt_score = report.get("score", "LOW")
        if _SCORE_ORDER.get(rpt_score, 0) > _SCORE_ORDER.get(merged["score"], 0):
            merged["score"] = rpt_score

    # Deduplicate sortable lists.
    for key, dedup in _MERGE_FIELDS:
        if dedup:
            merged[key] = sorted(set(merged[key]))

    return merged


@dataclass
class ImpactHook:
    """Run impact analysis on one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is analyzed separately and results are
    merged (max score, concatenated lists, deduplicated modules/tests).
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Must include ``symbol`` (name to analyze).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with ``impact`` dict in metadata on success.
        """
        symbol = params.get("symbol")
        if not symbol:
            return HookResult.fail("Missing required param 'symbol'")

        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path)
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        exclude_tests = bool(params.get("exclude_tests", False))

        try:
            from axm_ast.core.impact import analyze_impact

            symbols = [s.strip() for s in symbol.splitlines() if s.strip()]

            if len(symbols) == 1:
                report = analyze_impact(
                    working_dir,
                    symbols[0],
                    project_root=working_dir.parent,
                    exclude_tests=exclude_tests,
                )
                return HookResult.ok(impact=report)

            # Multiple symbols — analyze in parallel (I/O-bound: git log, file reads).
            def _analyze(sym: str) -> dict[str, Any]:
                return analyze_impact(
                    working_dir,
                    sym,
                    project_root=working_dir.parent,
                    exclude_tests=exclude_tests,
                )

            with ThreadPoolExecutor(max_workers=min(len(symbols), 4)) as pool:
                reports = list(pool.map(_analyze, symbols))
            merged = _merge_impact_reports(symbol, reports)
            return HookResult.ok(impact=merged)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Impact analysis failed: {exc}")


class DocImpactHook:
    """Run doc impact analysis on one or more symbols.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.  When *symbol* contains newline
    characters, each line is treated as a separate symbol.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
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
        if not symbol:
            return HookResult.fail("Missing required param 'symbol'")

        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path)
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        try:
            from axm_ast.core.doc_impact import analyze_doc_impact

            symbols = [s.strip() for s in symbol.splitlines() if s.strip()]
            report = analyze_doc_impact(working_dir, symbols)
            return HookResult.ok(**report)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Doc impact analysis failed: {exc}")
