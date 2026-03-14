"""ImpactHook — blast-radius analysis for a symbol.

Protocol hook that calls ``analyze_impact`` and returns the complete
impact report as ``HookResult`` metadata.  Registered as
``ast:impact`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

__all__ = ["ImpactHook"]


@dataclass
class ImpactHook:
    """Run impact analysis on a symbol and return the blast radius.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``symbol`` from *params*.
    The result is injected into session context via ``inject_result``.
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

            report = analyze_impact(
                working_dir,
                symbol,
                project_root=working_dir.parent,
            )

            return HookResult.ok(
                impact=report,
            )
        except Exception as exc:  # noqa: BLE001
            return HookResult.fail(f"Impact analysis failed: {exc}")
