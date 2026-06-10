"""Round-numbers strategy — reduce float precision."""

from __future__ import annotations

import json

from axm_smelt._types import JsonValue
from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["RoundNumbersStrategy"]


def _round_walk(data: JsonValue, precision: int) -> JsonValue:
    """Recursively round real float values, leaving strings verbatim."""
    if isinstance(data, dict):
        return {k: _round_walk(v, precision) for k, v in data.items()}
    if isinstance(data, list):
        return [_round_walk(item, precision) for item in data]
    if isinstance(data, float):
        return round(data, precision)
    return data


class RoundNumbersStrategy(SmeltStrategy):
    """Recursively round floats to *precision* decimal places."""

    def __init__(self, precision: int = 2) -> None:
        self._precision = precision

    @property
    def name(self) -> str:
        """Strategy identifier used in the registry."""
        return "round_numbers"

    @property
    def category(self) -> str:
        """Strategy category (``cosmetic``)."""
        return "cosmetic"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Round float values to the configured precision.

        Uses ``ctx.parsed`` for the JSON path; otherwise re-parses text
        that looks like JSON. Non-JSON text is returned unchanged (no
        regex rounding, which would corrupt floats embedded in strings).
        Propagates the rounded object as ``parsed`` on the returned
        context.
        """
        parsed = ctx.parsed
        if parsed is not None:
            rounded = _round_walk(parsed, self._precision)
            result = json.dumps(rounded, separators=(",", ":"), ensure_ascii=False)
            return SmeltContext(text=result, format=ctx.format, parsed=rounded)

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                rounded = _round_walk(data, self._precision)
                result = json.dumps(rounded, separators=(",", ":"), ensure_ascii=False)
                return SmeltContext(text=result, format=ctx.format, parsed=rounded)
            except (json.JSONDecodeError, ValueError):
                pass

        return ctx
