"""Compaction strategies."""

from __future__ import annotations

import logging

from axm_smelt.strategies.base import SmeltStrategy
from axm_smelt.strategies.collapse_whitespace import CollapseWhitespaceStrategy
from axm_smelt.strategies.compact_tables import CompactTablesStrategy
from axm_smelt.strategies.dedup_values import DedupValuesStrategy
from axm_smelt.strategies.drop_nulls import DropNullsStrategy
from axm_smelt.strategies.flatten import FlattenStrategy
from axm_smelt.strategies.minify import MinifyStrategy
from axm_smelt.strategies.round_numbers import RoundNumbersStrategy
from axm_smelt.strategies.strip_html_comments import StripHtmlCommentsStrategy
from axm_smelt.strategies.strip_quotes import StripQuotesStrategy
from axm_smelt.strategies.tabular import TabularStrategy

__all__ = ["get_preset", "get_strategy"]

_log = logging.getLogger(__name__)

_REGISTRY: dict[str, type[SmeltStrategy]] = {
    "minify": MinifyStrategy,
    "drop_nulls": DropNullsStrategy,
    "flatten": FlattenStrategy,
    "tabular": TabularStrategy,
    "round_numbers": RoundNumbersStrategy,
    "strip_quotes": StripQuotesStrategy,
    "dedup_values": DedupValuesStrategy,
    "collapse_whitespace": CollapseWhitespaceStrategy,
    "compact_tables": CompactTablesStrategy,
    "strip_html_comments": StripHtmlCommentsStrategy,
}

_PRESETS: dict[str, list[str]] = {
    "safe": ["minify", "collapse_whitespace"],
    "moderate": [
        "minify",
        "drop_nulls",
        "flatten",
        "dedup_values",
        "tabular",
        "strip_quotes",
        "collapse_whitespace",
        "compact_tables",
        "strip_html_comments",
    ],
    "aggressive": [
        "minify",
        "drop_nulls",
        "flatten",
        "tabular",
        "round_numbers",
        "dedup_values",
        "strip_quotes",
        "collapse_whitespace",
        "compact_tables",
        "strip_html_comments",
    ],
}


def get_strategy(name: str) -> SmeltStrategy:
    """Return a strategy instance by *name*."""
    cls = _REGISTRY.get(name)
    if cls is None:
        msg = f"Unknown strategy: {name}"
        raise ValueError(msg)
    return cls()


def get_preset(name: str) -> list[SmeltStrategy]:
    """Return a list of strategy instances for *name*."""
    keys = _PRESETS.get(name)
    if keys is None:
        msg = f"Unknown preset: {name}"
        raise ValueError(msg)
    strats: list[SmeltStrategy] = []
    for k in keys:
        try:
            strats.append(get_strategy(k))
        except ValueError:
            _log.debug("Skipping unavailable strategy: %s", k)
    return strats
