"""Unit tests for PackageCache — mock-based, no real I/O."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.cache import PackageCache

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


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
