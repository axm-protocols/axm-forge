"""Unit tests for CacheStatsTool (no I/O — the cache is read, never filled)."""

from __future__ import annotations

import os

import pytest

from axm_ast.core import cache as cache_mod
from axm_ast.core.cache import CacheLimits, CacheStats, PackageCache, clear_cache
from axm_ast.core.parser import ParseCacheStats
from axm_ast.tools.cache_stats import CacheStatsTool, build_stats_data

_MIB = 1024 * 1024


def _stats(**overrides: int | float | None) -> CacheStats:
    fields: dict[str, int | float | None] = {
        "entries": 0,
        "weight_bytes": 0,
        "max_weight_bytes": 1024 * _MIB,
        "ttl_seconds": 1800.0,
        "hits": 0,
        "misses": 0,
        "evicted_stale": 0,
        "evicted_dead": 0,
        "evicted_ttl": 0,
        "evicted_weight": 0,
    }
    fields.update(overrides)
    return CacheStats(**fields)


class TestCacheStatsToolIdentity:
    """Test the tool's static identity and discovery contract."""

    def test_name(self) -> None:
        """Tool registers under the ast_cache_stats name."""
        assert CacheStatsTool().name == "ast_cache_stats"

    def test_discoverable_as_cache_diagnostics(self) -> None:
        """Domain and tags let ``axm_search("cache")`` find the tool."""
        tool = CacheStatsTool()
        assert tool.domain == "ast"
        assert {"cache", "diagnostics"} <= tool.tags


class TestCacheStatsToolExecute:
    """Test execute() against the module-level cache singleton."""

    def test_cleared_cache_reports_zeros(self) -> None:
        """A reset cache reports no entry, no lookup and a null hit ratio."""
        clear_cache()
        result = CacheStatsTool().execute()
        assert result.success is True
        data = result.data
        assert (data["entries"], data["hits"], data["misses"]) == (0, 0, 0)
        assert data["weight_bytes"] == 0
        assert data["weight_mib"] == 0.0
        assert data["hit_ratio"] is None
        assert data["evicted_total"] == 0
        assert data["parse_cache"]["entries"] == 0
        assert data["pid"] == os.getpid()
        assert result.text is not None
        assert result.text.startswith("ast_cache_stats | ✓ |")

    def test_disabled_ceiling_reports_null_max(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cache without weight ceiling or TTL reports both as null."""
        unbounded = PackageCache(CacheLimits(max_weight_bytes=None, ttl_seconds=None))
        monkeypatch.setattr(cache_mod, "_cache", unbounded)
        result = CacheStatsTool().execute()
        assert result.data["max_weight_bytes"] is None
        assert result.data["max_weight_mib"] is None
        assert result.data["ttl_seconds"] is None
        assert result.text is not None
        assert "no ceiling · no ttl" in result.text

    def test_snapshot_error_returns_rendered_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing snapshot becomes a failure ToolResult with a text line."""

        def _broken() -> CacheStats:
            raise RuntimeError("lock poisoned")

        monkeypatch.setattr("axm_ast.tools.cache_stats.cache_stats", _broken)
        result = CacheStatsTool().execute()
        assert result.success is False
        assert result.error == "lock poisoned"
        assert result.text == "ast_cache_stats | ✗ | lock poisoned"

    def test_extra_arguments_are_ignored(self) -> None:
        """An injected ``path`` argument does not change the snapshot."""
        result = CacheStatsTool().execute(path="/nonexistent")
        assert result.success is True
        assert "entries" in result.data


class TestBuildStatsData:
    """Test the derived values computed from a snapshot."""

    def test_hit_ratio_and_eviction_total(self) -> None:
        """Hit ratio is hits / lookups; evictions are summed across reasons."""
        data = build_stats_data(
            _stats(hits=3, misses=1, evicted_stale=1, evicted_ttl=2, evicted_weight=1),
            ParseCacheStats(entries=5, max_entries=1024),
            pid=42,
        )
        assert data["hit_ratio"] == 0.75
        assert data["evicted_total"] == 4
        assert data["parse_cache"] == {"entries": 5, "max_entries": 1024}
        assert data["pid"] == 42

    def test_weights_are_converted_to_mib(self) -> None:
        """Estimated weight and ceiling are also reported in MiB."""
        data = build_stats_data(
            _stats(weight_bytes=3 * _MIB // 2, max_weight_bytes=512 * _MIB),
            ParseCacheStats(entries=0, max_entries=1024),
            pid=1,
        )
        assert data["weight_mib"] == 1.5
        assert data["max_weight_mib"] == 512.0
        assert data["weight_bytes"] == 3 * _MIB // 2

    def test_tiny_ceiling_is_not_rounded_to_zero(self) -> None:
        """A sub-0.01 MiB ceiling keeps two significant digits, never ``0.0``."""
        data = build_stats_data(
            _stats(max_weight_bytes=1000),
            ParseCacheStats(entries=0, max_entries=1024),
            pid=1,
        )
        assert data["max_weight_mib"] == 0.00095

    def test_raw_counters_are_preserved(self) -> None:
        """Every CacheStats field is carried verbatim as a plain JSON value."""
        stats = _stats(entries=2, hits=7, misses=2, evicted_dead=1)
        data = build_stats_data(stats, ParseCacheStats(0, 1024), pid=1)
        for field in CacheStats.__dataclass_fields__:
            assert data[field] == getattr(stats, field)
