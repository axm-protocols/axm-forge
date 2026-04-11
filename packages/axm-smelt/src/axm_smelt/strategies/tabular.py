"""Tabular strategy — convert homogeneous list[dict] to pipe-separated table."""

from __future__ import annotations

import json
from typing import Any

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["TabularStrategy"]


def _format_cell(value: object) -> str:
    """Format a single cell value for tabular output."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ": "), ensure_ascii=False)
    s = str(value)
    if "|" in s:
        return json.dumps(s)
    return s


def _collect_ordered_keys(items: list[dict[str, Any]]) -> list[str]:
    """Collect unique keys from dicts in first-seen insertion order."""
    keys: list[str] = []
    seen: set[str] = set()
    for item in items:
        for k in item:
            if k not in seen:
                keys.append(k)
                seen.add(k)
    return keys


def _render_rows(items: list[dict[str, Any]], keys: list[str]) -> list[str]:
    """Render each dict as a pipe-separated row according to *keys*."""
    rows: list[str] = []
    for item in items:
        cells = [_format_cell(item.get(k, "")) if k in item else "" for k in keys]
        rows.append("|".join(cells))
    return rows


def _to_table(data: object) -> str | None:
    """Convert a list of dicts to a pipe-separated table, or return None."""
    if not isinstance(data, list) or not data:
        return None
    if not all(isinstance(item, dict) for item in data):
        return None

    keys = _collect_ordered_keys(data)
    header = "|".join(keys)
    rows = _render_rows(data, keys)
    return "\n".join([header, *rows])


def _tabularize_dict(data: dict[str, object]) -> tuple[dict[str, object], bool]:
    """Recursively convert list-of-dict values to tables at any depth."""
    changed = False
    result: dict[str, object] = {}
    for k, v in data.items():
        if isinstance(v, list):
            table = _to_table(v)
            if table is not None:
                result[k] = table
                changed = True
            else:
                result[k] = v
        elif isinstance(v, dict):
            inner, inner_changed = _tabularize_dict(v)
            result[k] = inner
            if inner_changed:
                changed = True
        else:
            result[k] = v
    return result, changed


class TabularStrategy(SmeltStrategy):
    """Convert JSON arrays of objects to pipe-separated tables."""

    @property
    def name(self) -> str:
        return "tabular"

    @property
    def category(self) -> str:
        return "structural"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Convert homogeneous ``list[dict]`` to pipe-separated tables.

        Uses ``ctx.parsed`` when available to skip
        ``json.loads``. Recurses into nested dicts to tabularize
        inner arrays.
        """
        parsed = ctx.parsed
        if parsed is None:
            text = ctx.text
            stripped = text.strip()
            if not stripped or stripped[0] not in ("[", "{"):
                return ctx
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                return ctx

        if isinstance(parsed, list):
            table = _to_table(parsed)
            if table is not None:
                new_ctx = SmeltContext(text=table, format=ctx.format)
                new_ctx._parsed = None  # table text is not JSON-parseable
                return new_ctx
            return ctx

        if isinstance(parsed, dict):
            result, changed = _tabularize_dict(parsed)
            if changed:
                return SmeltContext(
                    text=json.dumps(result, separators=(",", ":"), ensure_ascii=False),
                    format=ctx.format,
                )

        return ctx
