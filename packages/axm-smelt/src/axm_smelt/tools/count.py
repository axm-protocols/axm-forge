"""SmeltCountTool — MCP entry point for smelt count."""

from __future__ import annotations

import json
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["SmeltCountTool"]


class SmeltCountTool(AXMTool):
    """Count tokens in text/data.

    Registered as ``smelt_count`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Count tokens in text or data using a specified tiktoken model — "
        "returns token count without modifying input"
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "smelt_count"

    def execute(
        self,
        *,
        data: str | Any = "",
        model: str = "o200k_base",
        **kwargs: Any,
    ) -> ToolResult:
        """Count tokens in data.

        Args:
            data: Text or data to count tokens for.
            model: Tiktoken model name.

        Returns:
            ToolResult with token count and model used.
        """
        try:
            if data is None:
                msg = "data must not be None"
                raise ValueError(msg)

            if not isinstance(data, str):
                data = json.dumps(data)

            from axm_smelt.core.counter import count

            tokens = count(data, model=model)

            return ToolResult(
                success=True,
                data={
                    "tokens": tokens,
                    "model": model,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
