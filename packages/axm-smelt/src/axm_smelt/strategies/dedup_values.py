"""Dedup-values strategy — collapse repeated string values in JSON."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.base import SmeltStrategy

__all__ = ["DedupValuesStrategy"]

_MIN_LENGTH = 20
_MIN_OCCURRENCES = 2


def _collect_strings(data: Any, strings: list[str]) -> None:
    """Walk data and collect string values."""
    if isinstance(data, str):
        if len(data) >= _MIN_LENGTH:
            strings.append(data)
    elif isinstance(data, dict):
        for v in data.values():
            _collect_strings(v, strings)
    elif isinstance(data, list):
        for item in data:
            _collect_strings(item, strings)


def _replace_strings(
    data: Any,
    lookup: dict[str, str],
) -> Any:
    """Replace repeated string values with short aliases."""
    if isinstance(data, str) and data in lookup:
        return lookup[data]
    if isinstance(data, dict):
        return {k: _replace_strings(v, lookup) for k, v in data.items()}
    if isinstance(data, list):
        return [_replace_strings(item, lookup) for item in data]
    return data


class DedupValuesStrategy(SmeltStrategy):
    """Replace frequently repeated long string values with aliases."""

    @property
    def name(self) -> str:
        return "dedup_values"

    @property
    def category(self) -> str:
        return "structural"

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        """Replace repeated long strings with short aliases.

        Uses ``ctx.parsed`` when available to skip
        ``json.loads``. Wraps the result in a ``{_refs, _data}``
        envelope.
        """
        parsed = ctx.parsed
        if parsed is None:
            text = ctx.text
            stripped = text.strip()
            if not stripped or stripped[0] not in ("{", "["):
                return ctx
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                return ctx

        strings: list[str] = []
        _collect_strings(parsed, strings)
        counts = Counter(strings)

        # Build alias map for repeated strings
        repeated = {
            s: count for s, count in counts.items() if count >= _MIN_OCCURRENCES
        }
        if not repeated:
            return ctx

        # Sort by savings (length * count) descending
        by_savings = sorted(repeated, key=lambda s: len(s) * repeated[s], reverse=True)

        lookup: dict[str, str] = {}
        aliases: dict[str, str] = {}
        for i, s in enumerate(by_savings):
            alias = f"$R{i}"
            lookup[s] = alias
            aliases[alias] = s

        replaced = _replace_strings(parsed, lookup)
        result = {"_refs": aliases, "_data": replaced}
        return SmeltContext(
            text=json.dumps(result, separators=(",", ":"), ensure_ascii=False),
            format=ctx.format,
        )
