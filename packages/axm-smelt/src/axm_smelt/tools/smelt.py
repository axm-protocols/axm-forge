"""SmeltTool — MCP entry point for axm-smelt."""

from __future__ import annotations

import json  # noqa: F401 — required for test patching (json.dumps guard)
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["SmeltTool"]


class SmeltTool(AXMTool):
    """Compact text/data for LLM consumption.

    Registered as ``smelt`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Compact text/JSON data for LLM consumption — apply minify, tabular, "
        "strip_quotes, and other strategies to reduce token count"
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "smelt"

    def execute(
        self,
        *,
        data: str | Any = "",
        strategies: list[str] | None = None,
        preset: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Run the smelt compaction pipeline.

        Args:
            data: Text or JSON data to compact.
            strategies: Optional list of strategy names.
            preset: Optional preset name.

        Returns:
            ToolResult with compacted output and metrics.
        """
        try:
            if data is None:
                msg = "data must not be None"
                raise ValueError(msg)

            from axm_smelt.core.pipeline import smelt

            if not isinstance(data, str):
                report = smelt(parsed=data, strategies=strategies, preset=preset)
            else:
                report = smelt(data, strategies=strategies, preset=preset)

            return ToolResult(
                success=True,
                data={
                    "compacted": report.compacted,
                    "format": report.format.value,
                    "original_tokens": report.original_tokens,
                    "compacted_tokens": report.compacted_tokens,
                    "savings_pct": round(report.savings_pct, 2),
                    "strategies_applied": report.strategies_applied,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
