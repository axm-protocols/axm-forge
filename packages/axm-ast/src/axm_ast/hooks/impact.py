"""ImpactHook — blast-radius analysis for one or more symbols.

Protocol hook that calls ``analyze_impact`` and returns the complete
impact report as ``HookResult`` metadata.  Registered as
``ast:impact`` via ``axm.hooks`` entry point.

Supports newline-separated symbol lists (e.g. from cross-phase
context).  Each symbol is analyzed independently and results are
merged with max-score semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

__all__ = ["ImpactHook"]

_SCORE_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
_MERGE_KEYS: tuple[str, ...] = (
    "callers",
    "type_refs",
    "reexports",
    "affected_modules",
    "test_files",
    "git_coupled",
)
_DEDUP_KEYS: frozenset[str] = frozenset({"affected_modules", "test_files"})


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

        try:
            from axm_ast.core.impact import analyze_impact

            symbols = [s.strip() for s in symbol.splitlines() if s.strip()]

            if len(symbols) == 1:
                report = analyze_impact(
                    working_dir,
                    symbols[0],
                    project_root=working_dir.parent,
                )
                return HookResult.ok(impact=report)

            # Multiple symbols — analyze each, merge results.
            merged: dict[str, Any] = {
                "symbol": symbol,
                "definitions": [],
                "callers": [],
                "type_refs": [],
                "reexports": [],
                "affected_modules": [],
                "test_files": [],
                "git_coupled": [],
                "score": "LOW",
            }
            for sym in symbols:
                report = analyze_impact(
                    working_dir,
                    sym,
                    project_root=working_dir.parent,
                )
                defn = report.get("definition")
                if defn:
                    merged["definitions"].append({"symbol": sym, **defn})
                for key in _MERGE_KEYS:
                    merged[key].extend(report.get(key, []))
                rpt_score = report.get("score", "LOW")
                if _SCORE_ORDER.get(rpt_score, 0) > _SCORE_ORDER.get(
                    merged["score"], 0
                ):
                    merged["score"] = rpt_score

            # Deduplicate sortable lists.
            for key in _DEDUP_KEYS:
                merged[key] = sorted(set(merged[key]))

            return HookResult.ok(impact=merged)
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Impact analysis failed: {exc}")
