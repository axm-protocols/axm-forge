"""SmeltCheckTool — MCP entry point for smelt check."""

from __future__ import annotations

from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_smelt._types import JsonValue

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
        data: JsonValue = "",
        **kwargs: object,
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
                report = check(
                    parsed=cast("dict[str, JsonValue] | list[JsonValue]", data)
                )
            else:
                report = check(data)

            ranked = sorted(
                report.strategy_estimates.items(),
                key=lambda kv: kv[1],
                reverse=True,
            )
            header = (
                f"smelt_check | {report.format.value} | {report.original_tokens} tok"
            )
            if ranked:
                body = "\n".join(f"  {name}: -{pct}%" for name, pct in ranked)
                text = f"{header}\n{body}"
            else:
                text = f"{header}\n  no waste detected"
            return ToolResult(
                success=True,
                data={
                    "format": report.format.value,
                    "tokens": report.original_tokens,
                    "strategy_estimates": report.strategy_estimates,
                },
                text=text,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
