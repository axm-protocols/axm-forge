"""Text renderer for CacheStatsTool dual-format ToolResult.

ast_cache_stats | ✓ | pid {pid} · {n} entries · {w}/{max} MiB · ttl {ttl}s
lookups: {n} · hits {h} · misses {m} · ratio {r}%
evictions: {n} · {reason} {count} ...
parse trees: {entries}/{max_entries}

Zero eviction reasons are omitted (the total is their sum); an unused cache
prints ``lookups: 0`` alone; a disabled bound prints ``no ceiling`` / ``no ttl``.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["render_failure_text", "render_text"]

_PERCENT = 100
_EVICTION_REASONS = ("stale", "dead", "ttl", "weight")


def _num(value: object) -> str:
    """Render a number without a trailing ``.0`` (``1024.0`` -> ``1024``)."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def _header(data: Mapping[str, object]) -> str:
    """Render pid, entry count, weight vs ceiling and idle TTL."""
    entries = data.get("entries")
    noun = "entry" if entries == 1 else "entries"
    weight = _num(data.get("weight_mib"))
    max_mib = data.get("max_weight_mib")
    if max_mib is None:
        size = f"{weight} MiB · no ceiling"
    else:
        size = f"{weight}/{_num(max_mib)} MiB"
    ttl = data.get("ttl_seconds")
    ttl_text = "no ttl" if ttl is None else f"ttl {_num(ttl)}s"
    return (
        f"ast_cache_stats | ✓ | pid {data.get('pid')} · {entries} {noun}"
        f" · {size} · {ttl_text}"
    )


def _lookups(data: Mapping[str, object]) -> str:
    """Render lookups with hits, misses and ratio, or ``0`` when unused."""
    hits = data.get("hits")
    misses = data.get("misses")
    ratio = data.get("hit_ratio")
    if not isinstance(ratio, (int, float)):
        return "lookups: 0"
    total = hits + misses if isinstance(hits, int) and isinstance(misses, int) else "?"
    return (
        f"lookups: {total} · hits {hits} · misses {misses}"
        f" · ratio {ratio * _PERCENT:.1f}%"
    )


def _evictions(data: Mapping[str, object]) -> str:
    """Render the eviction total followed by its non-zero reasons."""
    parts = [f"evictions: {data.get('evicted_total')}"]
    parts.extend(
        f"{reason} {count}"
        for reason in _EVICTION_REASONS
        if (count := data.get(f"evicted_{reason}"))
    )
    return " · ".join(parts)


def render_text(data: Mapping[str, object]) -> str:
    """Render the cache statistics payload as compact text."""
    parse = data.get("parse_cache")
    parse_map: Mapping[str, object] = parse if isinstance(parse, Mapping) else {}
    return "\n".join(
        [
            _header(data),
            _lookups(data),
            _evictions(data),
            f"parse trees: {parse_map.get('entries')}/{parse_map.get('max_entries')}",
        ]
    )


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation."""
    return f"ast_cache_stats | ✗ | {error}"
