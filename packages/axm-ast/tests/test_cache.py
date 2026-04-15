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
        assert len(result.modules) >= 1

    def test_clear_cache_then_get(self) -> None:
        """get_package → clear_cache → get_package works correctly."""
        first = get_package(SAMPLE_PKG)
        clear_cache()
        second = get_package(SAMPLE_PKG)
        # Both return valid PackageInfo, but different objects after clear
        assert first.name == second.name
        assert first.name == second.name


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestPackageCacheEdgeCases:
    """Edge cases for PackageCache."""

    def test_nonexistent_path(self) -> None:
        """Non-existent path raises ValueError (from analyze_package)."""
        cache = PackageCache()
        with pytest.raises(ValueError):
            cache.get(Path("/nonexistent/path"))

    def test_empty_package(self, tmp_path: Path) -> None:
        """Empty package with only __init__.py returns 1 module."""
        pkg = tmp_path / "empty_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Empty."""')
        cache = PackageCache()
        result = cache.get(pkg)
        assert len(result.modules) >= 1


# ─── Filesystem change invalidation (AXM-166) ───────────────────────────────


class TestPackageCacheFilesystemInvalidation:
    """Cache invalidates when .py files are added or deleted."""

    def test_cache_hit_unchanged(self, tmp_path: Path) -> None:
        """No filesystem changes → same cached object returned."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        (pkg / "mod_a.py").write_text('"""Module A."""')

        cache = PackageCache()
        first = cache.get(pkg)
        second = cache.get(pkg)
        assert first is second  # exact same object — no re-parse

    def test_cache_invalidation_on_delete(self, tmp_path: Path) -> None:
        """Deleting a .py file → cache invalidates, deleted module absent."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        mod_b = pkg / "mod_b.py"
        mod_b.write_text('"""Module B."""\ndef hello() -> str:\n    return "hi"')

        cache = PackageCache()
        first = cache.get(pkg)
        module_names = [m.path.stem for m in first.modules]
        assert "mod_b" in module_names

        # Delete the file
        mod_b.unlink()
        second = cache.get(pkg)
        assert second is not first  # different object — re-parsed
        module_names_after = [m.path.stem for m in second.modules]
        assert "mod_b" not in module_names_after

    def test_cache_invalidation_on_add(self, tmp_path: Path) -> None:
        """Adding a .py file → cache invalidates, new module present."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')

        cache = PackageCache()
        first = cache.get(pkg)
        assert len(first.modules) == 1

        # Add a new file
        (pkg / "new_mod.py").write_text(
            '"""New."""\ndef greet() -> str:\n    return "hello"'
        )
        second = cache.get(pkg)
        assert second is not first  # different object — re-parsed
        module_names = [m.path.stem for m in second.modules]
        assert "new_mod" in module_names

    def test_clear_cache_full_reset(self, tmp_path: Path) -> None:
        """clear() still forces full re-parse on next call."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')

        cache = PackageCache()
        first = cache.get(pkg)
        cache.clear()
        second = cache.get(pkg)
        assert second is not first  # different object after clear
        assert first.name == second.name  # same package


# ─── Content modification invalidation (F4) ─────────────────────────────────


class TestPackageCacheMtimeInvalidation:
    """Cache invalidates when .py file content is modified (F4)."""

    def test_cache_invalidation_on_modify(self, tmp_path: Path) -> None:
        """Modifying a .py file's content → cache invalidates, re-parses."""
        import time

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        mod = pkg / "mod.py"
        mod.write_text(
            '"""Mod."""\ndef hello() -> str:\n    """Hello."""\n    return "hi"'
        )

        cache = PackageCache()
        first = cache.get(pkg)
        assert any(f.name == "hello" for m in first.modules for f in m.functions)

        # Modify the file content (sleep ensures mtime changes)
        time.sleep(0.05)
        mod.write_text(
            '"""Mod."""\ndef goodbye() -> str:\n    """Goodbye."""\n    return "bye"'
        )

        second = cache.get(pkg)
        assert second is not first  # different object — re-parsed
        func_names = [f.name for m in second.modules for f in m.functions]
        assert "goodbye" in func_names
        assert "hello" not in func_names


# ─── Call-site caching (F8) ──────────────────────────────────────────────────


class TestPackageCacheGetCalls:
    """Tests for get_calls() — cached call-site extraction (F8)."""

    def test_get_calls_returns_dict(self, tmp_path: Path) -> None:
        """get_calls() returns a dict keyed by module name."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\ndef greet() -> str:\n    """Greet."""\n    return "hi"'
        )
        (pkg / "cli.py").write_text(
            '"""CLI."""\ndef main() -> None:\n    """Main."""\n    greet()'
        )

        cache = PackageCache()
        calls = cache.get_calls(pkg)
        assert isinstance(calls, dict)
        assert len(calls) >= 1

    def test_get_calls_caching(self, tmp_path: Path) -> None:
        """get_calls() returns the same object on second call (cached)."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\ndef greet() -> str:\n    """Greet."""\n    return "hi"'
        )

        cache = PackageCache()
        first = cache.get_calls(pkg)
        second = cache.get_calls(pkg)
        assert first is second  # exact same dict — no re-extraction

    def test_get_calls_invalidation_on_modify(self, tmp_path: Path) -> None:
        """Modifying a file evicts both PackageInfo and call-sites."""
        import time

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""')
        mod = pkg / "mod.py"
        mod.write_text('"""Mod."""\ndef setup() -> None:\n    """Setup."""\n    foo()')

        cache = PackageCache()
        first_calls = cache.get_calls(pkg)
        # Verify foo() is found
        all_symbols = [c.symbol for calls in first_calls.values() for c in calls]
        assert "foo" in all_symbols

        # Modify file
        time.sleep(0.05)
        mod.write_text('"""Mod."""\ndef setup() -> None:\n    """Setup."""\n    bar()')

        second_calls = cache.get_calls(pkg)
        assert second_calls is not first_calls  # re-extracted
        all_symbols = [c.symbol for calls in second_calls.values() for c in calls]
        assert "bar" in all_symbols
        assert "foo" not in all_symbols
