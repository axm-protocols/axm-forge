"""SmeltCountTool — MCP entry point for smelt count."""

from __future__ import annotations

import sys

from axm.tools.base import AXMTool, ToolResult

from axm_smelt._types import JsonValue
from axm_smelt.core.input_source import resolve_text_source

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
        data: JsonValue = "",
        input_path: str | None = None,
        model: str = "o200k_base",
        **kwargs: object,
    ) -> ToolResult:
        """Count tokens in data.

        Args:
            data: Text or data to count tokens for.
            input_path: Optional UTF-8 input file used when data is empty.
            model: Tiktoken model name.

        Returns:
            ToolResult with token count and model used.
        """
        try:
            if data is None:
                msg = "data must not be None"
                raise ValueError(msg)

            if isinstance(data, str):
                data = resolve_text_source(data, input_path, stdin=sys.stdin)

            if not isinstance(data, str):
                # Reuse the pipeline's canonical serialization
                # (separators=(",", ":") + sort_keys=True) so smelt_count
                # measures the same baseline that smelt later tokenizes.
                from axm_smelt.core.models import SmeltContext

                data = SmeltContext(parsed=data).text

            from axm_smelt.core.counter import count_with_backend

            tokens, backend = count_with_backend(data, model=model)

            return ToolResult(
                success=True,
                data={
                    "tokens": tokens,
                    "model": model,
                    "counter_backend": backend.value,
                },
                text=(
                    f"smelt_count | {tokens} tokens | {len(data)} chars | "
                    f"{model} | {backend.value}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
