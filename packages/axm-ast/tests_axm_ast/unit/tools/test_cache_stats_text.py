"""Unit tests for the CacheStatsTool dual-format text renderers."""

from __future__ import annotations

from axm_ast.tools.cache_stats_text import render_failure_text, render_text


def _data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "entries": 3,
        "weight_bytes": 14_890_000,
        "max_weight_bytes": 1_073_741_824,
        "ttl_seconds": 1800.0,
        "hits": 8,
        "misses": 2,
        "evicted_stale": 1,
        "evicted_dead": 0,
        "evicted_ttl": 2,
        "evicted_weight": 0,
        "weight_mib": 14.2,
        "max_weight_mib": 1024.0,
        "hit_ratio": 0.8,
        "evicted_total": 3,
        "parse_cache": {"entries": 12, "max_entries": 1024},
        "pid": 4242,
    }
    data.update(overrides)
    return data


class TestRenderText:
    """Test the success-path renderer."""

    def test_full_rendering(self) -> None:
        """Header, lookups, non-zero eviction reasons and parse trees."""
        assert render_text(_data()).splitlines() == [
            "ast_cache_stats | ✓ | pid 4242 · 3 entries · 14.2/1024 MiB · ttl 1800s",
            "lookups: 10 · hits 8 · misses 2 · ratio 80.0%",
            "evictions: 3 · stale 1 · ttl 2",
            "parse trees: 12/1024",
        ]

    def test_unused_cache_collapses_lookups(self) -> None:
        """Before any lookup the hit/miss breakdown and ratio are omitted."""
        text = render_text(
            _data(entries=0, hits=0, misses=0, hit_ratio=None, evicted_total=0)
        )
        assert "lookups: 0\n" in text
        assert "ratio" not in text

    def test_no_eviction_prints_total_only(self) -> None:
        """Zero-count eviction reasons are left out."""
        text = render_text(_data(evicted_total=0, evicted_stale=0, evicted_ttl=0))
        assert "evictions: 0\n" in text

    def test_disabled_bounds_render_as_words(self) -> None:
        """A disabled ceiling or TTL is named, never rendered as ``None``."""
        text = render_text(_data(max_weight_mib=None, ttl_seconds=None))
        header = text.splitlines()[0]
        assert header.endswith("· 14.2 MiB · no ceiling · no ttl")
        assert "None" not in header

    def test_singular_entry(self) -> None:
        """One cached package reads ``1 entry``."""
        assert "· 1 entry ·" in render_text(_data(entries=1))


class TestRenderFailureText:
    """Test the failure-path renderer."""

    def test_failure_renders_error_message(self) -> None:
        """The failure line carries the error string after the ✗ marker."""
        assert render_failure_text(error="boom") == "ast_cache_stats | ✗ | boom"
