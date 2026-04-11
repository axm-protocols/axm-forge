"""SmeltCheckTool — MCP entry point for smelt check."""

from __future__ import annotations

from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["SmeltCheckTool"]


class SmeltCheckTool(AXMTool):
    """Analyze text/data for token waste without transforming it.

    Registered as ``smelt_check`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Analyze text or JSON data for token waste — returns detected format, "
        "token count, and per-strategy saving estimates without modifying input"
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "smelt_check"

    def execute(
        self,
        *,
        data: str | Any = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Analyze data for token reduction opportunities.

        Args:
            data: Text or JSON data to analyze.

        Returns:
            ToolResult with format, token count, and strategy estimates.
        """
        try:
            if data is None:
                msg = "data must not be None"
                raise ValueError(msg)

            from axm_smelt.core.pipeline import check

            if not isinstance(data, str):
                report = check(parsed=data)
            else:
                report = check(data)

            return ToolResult(
                success=True,
                data={
                    "format": report.format.value,
                    "tokens": report.original_tokens,
                    "strategy_estimates": report.strategy_estimates,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
