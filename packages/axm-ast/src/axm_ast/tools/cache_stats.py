"""CacheStatsTool — read the in-process package and parse-tree cache counters.

Exposes :func:`axm_ast.core.cache.cache_stats` and
:func:`axm_ast.core.parser.parse_cache_stats` through the tool catalog, so the
long-lived shared MCP daemon can report its own cache singleton. Read-only: it
never parses a package nor touches the filesystem.
"""

from __future__ import annotations

import dataclasses
import logging
import os

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.cache import CacheStats, cache_stats
from axm_ast.core.parser import ParseCacheStats, parse_cache_stats
from axm_ast.tools._base import safe_execute
from axm_ast.tools.cache_stats_text import render_failure_text, render_text

logger = logging.getLogger(__name__)

__all__ = ["CacheStatsTool", "build_stats_data"]

_MIB = 1024 * 1024
_MIB_DIGITS = 2
_MIB_SMALL = 0.01
_RATIO_DIGITS = 4


def _mib(size_bytes: int) -> float:
    """Convert bytes to MiB, keeping two significant digits below 0.01 MiB.

    A plain two-decimal rounding would report a tiny non-zero weight or
    ceiling as ``0.0`` — a ceiling of ``0`` reads as "evict everything".
    """
    value = size_bytes / _MIB
    if value >= _MIB_SMALL or value == 0:
        return round(value, _MIB_DIGITS)
    return float(f"{value:.2g}")


def build_stats_data(
    stats: CacheStats,
    parse: ParseCacheStats,
    *,
    pid: int,
) -> dict[str, object]:
    """Build the JSON payload: raw counters plus derived values.

    Args:
        stats: Snapshot of the package cache.
        parse: Snapshot of the parsed-tree LRU.
        pid: Process whose singleton the snapshot describes.

    Returns:
        The :class:`CacheStats` fields, ``weight_mib``, ``max_weight_mib``
        (``None`` when the ceiling is disabled), ``hit_ratio`` (``None``
        before the first lookup), ``evicted_total``, ``parse_cache`` and
        ``pid``.
    """
    lookups = stats.hits + stats.misses
    max_bytes = stats.max_weight_bytes
    return {
        **dataclasses.asdict(stats),
        "weight_mib": _mib(stats.weight_bytes),
        "max_weight_mib": (None if max_bytes is None else _mib(max_bytes)),
        "hit_ratio": round(stats.hits / lookups, _RATIO_DIGITS) if lookups else None,
        "evicted_total": (
            stats.evicted_stale
            + stats.evicted_dead
            + stats.evicted_ttl
            + stats.evicted_weight
        ),
        "parse_cache": dataclasses.asdict(parse),
        "pid": pid,
    }


class CacheStatsTool(AXMTool):
    """Report the axm-ast cache counters of the serving process.

    Registered as ``ast_cache_stats`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Read-only diagnostics of the axm-ast in-process caches (package cache"
        " entries, estimated MiB vs ceiling, hits/misses, evictions by reason,"
        " parse-tree LRU) of the serving process — call it on the shared MCP"
        " daemon to observe its memory. No parameters, no parsing."
    )
    domain = "ast"
    tags = frozenset({"cache", "diagnostics", "memory", "stats"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "ast_cache_stats"

    @safe_execute
    def execute(self, **kwargs: object) -> ToolResult:
        """Report axm-ast cache statistics of the serving process (read-only).

        Takes no parameters; extra keyword arguments are ignored. Never parses
        a package nor reads the filesystem.

        Returns:
            ToolResult whose ``data`` holds the package-cache counters
            (``entries``, ``weight_bytes``, ``max_weight_bytes``,
            ``ttl_seconds``, ``hits``, ``misses``, ``evicted_*``), the derived
            ``weight_mib``, ``max_weight_mib``, ``hit_ratio`` and
            ``evicted_total``, the ``parse_cache`` occupancy and the ``pid``.
        """
        try:
            data = build_stats_data(cache_stats(), parse_cache_stats(), pid=os.getpid())
        except Exception as exc:  # MCP boundary: any error -> failure
            logger.warning("ast_cache_stats failed: %s", exc, exc_info=True)
            error = str(exc)
            return ToolResult(
                success=False, error=error, text=render_failure_text(error=error)
            )
        return ToolResult(success=True, data=data, text=render_text(data))
