"""Drop-nulls strategy — remove empty values recursively."""

from __future__ import annotations

import json
from typing import Any

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["DropNullsStrategy"]


def _is_empty(value: Any) -> bool:
    """Return True if *value* is considered empty."""
    return value is None or value in ("", [], {})


def _clean(data: Any) -> Any:
    """Recursively remove empty values (bottom-up)."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            v = _clean(v)
            if not _is_empty(v):
                cleaned[k] = v
        return cleaned
    if isinstance(data, list):
        return [_clean(item) for item in data if not _is_empty(_clean(item))]
    return data


class DropNullsStrategy(SmeltStrategy):
    """Recursively remove None, empty strings, empty lists, and empty dicts."""

    @property
    def name(self) -> str:
        return "drop_nulls"

    @property
    def category(self) -> str:
        return "structural"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Remove empty values from JSON data.

        Uses ``ctx.parsed`` when available to skip
        ``json.loads``. Propagates the cleaned object as
        ``parsed`` on the returned context.
        """
        parsed = ctx.parsed
        if parsed is not None:
            cleaned = _clean(parsed)
            result = json.dumps(cleaned, separators=(",", ":"), ensure_ascii=False)
            new_ctx = SmeltContext(text=result, format=ctx.format)
            new_ctx._parsed = cleaned
            return new_ctx

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                cleaned = _clean(data)
                result = json.dumps(cleaned, separators=(",", ":"), ensure_ascii=False)
                new_ctx = SmeltContext(text=result, format=ctx.format)
                new_ctx._parsed = cleaned
                return new_ctx
            except (json.JSONDecodeError, ValueError):
                pass

        return ctx
