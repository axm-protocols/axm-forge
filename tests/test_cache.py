"""Tests for PackageCache — LRU caching of PackageInfo results.

TDD: Tests written first, then cache.py implementation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.cache import PackageCache, clear_cache, get_package

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── PackageCache unit tests ─────────────────────────────────────────────────


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

    def test_cache_clear(self) -> None:
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            cache.get(SAMPLE_PKG)
            cache.clear()
            cache.get(SAMPLE_PKG)
            assert mock.call_count == 2


class TestPackageCachePaths:
    """Different paths produce independent cache entries."""

    def test_different_paths_independent(self, tmp_path: Path) -> None:
        cache = PackageCache()
        pkg_a = tmp_path / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text('"""Package A."""')
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text('"""Package B."""')

        result_a = cache.get(pkg_a)
        result_b = cache.get(pkg_b)
        assert result_a is not result_b
        assert result_a.name == "pkg_a"
        assert result_b.name == "pkg_b"

    def test_resolved_paths(self, tmp_path: Path) -> None:
        """Relative and absolute paths to the same dir share cache entry."""
        cache = PackageCache()
        with patch("axm_ast.core.cache.analyze_package") as mock:
            mock.return_value = MagicMock(name="PackageInfo")
            cache.get(tmp_path / "." / "sub" / "..")
            cache.get(tmp_path.resolve())
            mock.assert_called_once()


# ─── Public API functions ────────────────────────────────────────────────────


class TestGetPackagePublicApi:
    """Tests for get_package() module-level function."""

    def test_get_package_returns_package_info(self) -> None:
        result = get_package(SAMPLE_PKG)
        assert result.name == "sample_pkg"
        assert len(result.modules) >= 3

    def test_clear_cache_then_get(self) -> None:
        """get_package → clear_cache → get_package works correctly."""
        first = get_package(SAMPLE_PKG)
        clear_cache()
        second = get_package(SAMPLE_PKG)
        # Both return valid PackageInfo, but different objects after clear
        assert first.name == second.name
        assert len(first.modules) == len(second.modules)


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestPackageCacheEdgeCases:
    """Edge cases for PackageCache."""

    def test_nonexistent_path(self) -> None:
        """Non-existent path raises ValueError (from analyze_package)."""
        cache = PackageCache()
        with pytest.raises(ValueError, match="not a directory"):
            cache.get(Path("/nonexistent/path"))

    def test_empty_package(self, tmp_path: Path) -> None:
        """Empty package with only __init__.py returns 1 module."""
        pkg = tmp_path / "empty_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Empty."""')
        cache = PackageCache()
        result = cache.get(pkg)
        assert len(result.modules) == 1
