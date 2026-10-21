"""Unit + integration tests for axm_ast.core.cache.

Covers PackageCache mock-based behavior (cache miss/hit/clear, path
resolution, edge cases) and the module-level get_package/clear_cache
functions (integration with real fixture parsing).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.cache import (
    CacheLimits,
    CacheStats,
    PackageCache,
    cache_stats,
    clear_cache,
    get_package,
)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ────────────────────────────────────────────────────────────────────────────
# PackageCache — mock-based unit tests (no real I/O)
# ────────────────────────────────────────────────────────────────────────────


class TestPackageCacheMiss:
    """Cache miss calls analyze_package."""

    def test_cache_miss_calls_analyze(self) -> None:
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            result = cache.get(SAMPLE_PKG)
            mock.assert_called_once()
            assert result is mock.return_value


class TestPackageCacheHit:
    """Cache hit returns same object without re-parsing."""

    def test_cache_hit_no_reparse(self) -> None:
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            first = cache.get(SAMPLE_PKG)
            second = cache.get(SAMPLE_PKG)
            mock.assert_called_once()
            assert first is second


class TestPackageCacheClear:
    """Cache clear invalidates all entries."""

    def test_cache_clear_forces_reparse(self) -> None:
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            cache.get(SAMPLE_PKG)
            cache.clear()
            cache.get(SAMPLE_PKG)
            assert mock.call_count == 2


class TestPackageCacheResolvedPaths:
    """Equivalent paths share cache entries."""

    def test_resolved_paths(self, tmp_path: Path) -> None:
        """Relative and absolute paths to the same dir share cache entry."""
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            cache.get(tmp_path / "." / "sub" / "..")
            cache.get(tmp_path.resolve())
            mock.assert_called_once()


class TestPackageCacheEdgeCases:
    """Edge cases — no I/O."""

    def test_nonexistent_path(self) -> None:
        """Non-existent path raises ValueError."""
        cache = PackageCache()
        with pytest.raises(ValueError):
            cache.get(Path("/nonexistent/path"))


class TestCacheLimitsFromEnv:
    """Environment configuration of the memory bounds."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AXM_AST_CACHE_MAX_MB", raising=False)
        monkeypatch.delenv("AXM_AST_CACHE_TTL_S", raising=False)

    def test_defaults_without_configuration(self) -> None:
        limits = CacheLimits.from_env()
        assert limits == CacheLimits()
        assert limits.max_weight_bytes == 1024 * 1024 * 1024
        assert limits.ttl_seconds == 1800.0

    def test_values_are_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AXM_AST_CACHE_MAX_MB", "256")
        monkeypatch.setenv("AXM_AST_CACHE_TTL_S", "90.5")
        limits = CacheLimits.from_env()
        assert limits.max_weight_bytes == 256 * 1024 * 1024
        assert limits.ttl_seconds == 90.5

    def test_zero_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AXM_AST_CACHE_MAX_MB", "0")
        monkeypatch.setenv("AXM_AST_CACHE_TTL_S", " 0 ")
        limits = CacheLimits.from_env()
        assert limits.max_weight_bytes is None
        assert limits.ttl_seconds is None

    @pytest.mark.parametrize("raw", ["abc", "-5", "nan", "inf"])
    def test_invalid_falls_back_to_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        raw: str,
    ) -> None:
        monkeypatch.setenv("AXM_AST_CACHE_MAX_MB", raw)
        monkeypatch.setenv("AXM_AST_CACHE_TTL_S", raw)
        assert CacheLimits.from_env() == CacheLimits()
        assert "AXM_AST_CACHE_MAX_MB" in caplog.text
        assert "AXM_AST_CACHE_TTL_S" in caplog.text


class TestPackageCacheStatsEmpty:
    """A fresh cache reports zeroed counters and its limits."""

    def test_fresh_cache_stats(self) -> None:
        limits = CacheLimits(max_weight_bytes=123, ttl_seconds=None)
        stats = PackageCache(limits).stats()
        assert stats == CacheStats(
            entries=0,
            weight_bytes=0,
            max_weight_bytes=123,
            ttl_seconds=None,
            hits=0,
            misses=0,
            evicted_stale=0,
            evicted_dead=0,
            evicted_ttl=0,
            evicted_weight=0,
        )


# ────────────────────────────────────────────────────────────────────────────
# get_package / clear_cache — integration with real fixture parsing
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_get_package_returns_package_info() -> None:
    result = get_package(SAMPLE_PKG)
    assert result.name == "sample_pkg"
    assert len(result.modules) >= 1


@pytest.mark.integration
def test_clear_cache_then_get() -> None:
    """get_package → clear_cache → get_package re-parses correctly."""
    first = get_package(SAMPLE_PKG)
    clear_cache()
    second = get_package(SAMPLE_PKG)
    assert first is not second
    assert first.name == second.name


@pytest.mark.integration
def test_cache_stats_reflects_global_cache() -> None:
    """cache_stats() snapshots the singleton used by get_package."""
    clear_cache()
    get_package(SAMPLE_PKG)
    get_package(SAMPLE_PKG)
    stats = cache_stats()
    assert (stats.entries, stats.hits, stats.misses) == (1, 1, 1)
    assert stats.weight_bytes > 0


# ────────────────────────────────────────────────────────────────────────────
# Docstring contract — best-effort double-check / benign race
# ────────────────────────────────────────────────────────────────────────────


def test_get_calls_docstring_documents_benign_race() -> None:
    """AC1: get_calls/get_call_index docstrings document the benign race.

    Both methods use compute-outside-lock + re-check-before-write
    (best-effort double-checked locking); the docstrings must explain
    why the resulting race is benign.
    """
    for doc in (PackageCache.get_calls.__doc__, PackageCache.get_call_index.__doc__):
        assert doc is not None
        lowered = doc.lower()
        assert "double-check" in lowered
        assert "benign" in lowered
        assert "first write wins" in lowered
