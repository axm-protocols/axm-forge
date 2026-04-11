"""Flatten strategy — collapse single-child wrapper dicts."""

from __future__ import annotations

import json
from typing import Any

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["FlattenStrategy"]


def _flatten_dict(
    data: dict[str, Any],
    max_depth: int | None,
    depth: int = 0,
) -> dict[str, Any]:
    """Collapse single-child wrapper dicts into dotted keys."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if (
            isinstance(value, dict)
            and len(value) == 1
            and (max_depth is None or depth < max_depth)
        ):
            inner_key, inner_value = next(iter(value.items()))
            merged_key = f"{key}.{inner_key}"
            # Recursively flatten the merged result
            if isinstance(inner_value, dict) and len(inner_value) == 1:
                sub = _flatten_dict({merged_key: inner_value}, max_depth, depth + 1)
                result.update(sub)
            else:
                result[merged_key] = _flatten_node(inner_value, max_depth, depth + 1)
        else:
            result[key] = _flatten_node(value, max_depth, depth)
    return result


def _flatten_node(data: Any, max_depth: int | None, depth: int = 0) -> Any:
    """Recursively flatten dicts in any structure."""
    if isinstance(data, dict):
        return _flatten_dict(data, max_depth, depth)
    if isinstance(data, list):
        return [_flatten_node(item, max_depth, depth) for item in data]
    return data


class FlattenStrategy(SmeltStrategy):
    """Collapse single-child wrapper dicts into dotted keys."""

    def __init__(self, max_depth: int | None = None) -> None:
        self._max_depth = max_depth

    @property
    def name(self) -> str:
        return "flatten"

    @property
    def category(self) -> str:
        return "structural"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Collapse single-child wrapper dicts into dotted keys.

        Uses ``ctx.parsed`` when available to skip
        ``json.loads``. Propagates the flattened object as
        ``parsed`` on the returned context.
        """
        parsed = ctx.parsed
        if parsed is not None:
            flattened = _flatten_node(parsed, self._max_depth)
            result = json.dumps(
                flattened,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            new_ctx = SmeltContext(text=result, format=ctx.format)
            new_ctx._parsed = flattened
            return new_ctx

        text = ctx.text
        stripped = text.strip()
        if not stripped:
            return ctx

        if stripped[0] in ("{", "["):
            try:
                data = json.loads(stripped)
                flattened = _flatten_node(data, self._max_depth)
                result = json.dumps(
                    flattened,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                new_ctx = SmeltContext(text=result, format=ctx.format)
                new_ctx._parsed = flattened
                return new_ctx
            except (json.JSONDecodeError, ValueError):
                pass

        return ctx
