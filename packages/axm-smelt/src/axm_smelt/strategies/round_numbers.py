"""Round-numbers strategy — reduce float precision."""

from __future__ import annotations

import json
import re
from typing import Any

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["RoundNumbersStrategy"]


_FLOAT_RE = re.compile(r"-?\d+\.\d{3,}")


def _round_in_str(text: str, precision: int) -> str:
    """Round float literals embedded in a string value."""
    return _FLOAT_RE.sub(
        lambda m: str(round(float(m.group()), precision)),
        text,
    )


def _round_walk(data: Any, precision: int) -> Any:
    """Recursively round float values (and floats embedded in strings)."""
    if isinstance(data, dict):
        return {k: _round_walk(v, precision) for k, v in data.items()}
    if isinstance(data, list):
        return [_round_walk(item, precision) for item in data]
    if isinstance(data, float):
        return round(data, precision)
    if isinstance(data, str):
        return _round_in_str(data, precision)
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

    def _round_text(self, text: str) -> str:
        """Round float literals found in plain text (e.g. tabular output)."""
        return _round_in_str(text, self._precision)

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Round float values to the configured precision.

        Uses ``ctx.parsed`` for the JSON path and falls back to
        regex-based rounding on plain text (e.g. post-tabular output).
        Propagates the rounded object as ``parsed`` on the returned
        context.
        """
        parsed = ctx.parsed
        if parsed is not None:
            rounded = _round_walk(parsed, self._precision)
            result = json.dumps(rounded, separators=(",", ":"), ensure_ascii=False)
            new_ctx = SmeltContext(text=result, format=ctx.format)
            new_ctx._parsed = rounded
            return new_ctx

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                rounded = _round_walk(data, self._precision)
                result = json.dumps(rounded, separators=(",", ":"), ensure_ascii=False)
                new_ctx = SmeltContext(text=result, format=ctx.format)
                new_ctx._parsed = rounded
                return new_ctx
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: round floats in plain text (post-tabular output, etc.)
        result = self._round_text(text)
        if result != text:
            new_ctx = SmeltContext(text=result, format=ctx.format)
            new_ctx._parsed = None  # non-JSON text, prevent reparsing
            return new_ctx
        return ctx
