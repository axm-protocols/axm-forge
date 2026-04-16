"""Integration tests for PackageCache — filesystem invalidation and real I/O.

Tests that exercise cache behavior with real file creation, deletion, and
modification via tmp_path.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_ast.core.cache import PackageCache, clear_cache, get_package

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── Path handling ──────────────────────────────────────────────────────────


class TestPackageCachePaths:
    """Different paths produce independent cache entries."""

    @pytest.mark.integration
    def test_different_paths_independent(self, tmp_path: Path) -> None:
        cache = PackageCache()
        pkg_a = tmp_path / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text('"""Package A."""')
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text('"""Package B."""')

        with patch(
            "axm_ast.core.cache.analyze_package",
            wraps=__import__(
                "axm_ast.core.cache", fromlist=["analyze_package"]
            ).analyze_package,
        ) as spy:
            result_a = cache.get(pkg_a)
            result_b = cache.get(pkg_b)
            assert spy.call_count == 2
        assert result_a.name == "pkg_a"
        assert result_b.name == "pkg_b"


# ─── Public API functions ───────────────────────────────────────────────────


class TestGetPackageIntegration:
    """Tests for get_package() / clear_cache() with real fixture I/O."""

    @pytest.mark.integration
    def test_get_package_returns_package_info(self) -> None:
        result = get_package(SAMPLE_PKG)
        assert result.name == "sample_pkg"
        assert len(result.modules) >= 1

    @pytest.mark.integration
    def test_clear_cache_then_get(self) -> None:
        """get_package → clear_cache → get_package re-parses correctly."""
        first = get_package(SAMPLE_PKG)
        clear_cache()
        second = get_package(SAMPLE_PKG)
        assert first is not second
        assert first.name == second.name


# ─── Edge cases ─────────────────────────────────────────────────────────────


class TestPackageCacheEdgeCases:
    """Edge cases for PackageCache with real I/O."""

    @pytest.mark.integration
    def test_empty_package(self, tmp_path: Path) -> None:
        """Empty package with only __init__.py returns exactly 1 module."""
        pkg = tmp_path / "empty_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Empty."""')
        cache = PackageCache()
        result = cache.get(pkg)
        assert len(result.modules) == 1


# ─── Filesystem change invalidation (AXM-166) ──────────────────────────────


class TestPackageCacheFilesystemInvalidation:
    """Cache invalidates when .py files are added or deleted."""

    @pytest.mark.integration
    def test_cache_hit_unchanged(self, tmp_path: Path) -> None:
        """No filesystem changes → same cached object returned."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        (pkg / "mod_a.py").write_text('"""Module A."""')

        cache = PackageCache()
        first = cache.get(pkg)
        second = cache.get(pkg)
        assert first is second

    @pytest.mark.integration
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

        mod_b.unlink()
        second = cache.get(pkg)
        assert second is not first
        module_names_after = [m.path.stem for m in second.modules]
        assert "mod_b" not in module_names_after

    @pytest.mark.integration
    def test_cache_invalidation_on_add(self, tmp_path: Path) -> None:
        """Adding a .py file → cache invalidates, new module present."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')

        cache = PackageCache()
        first = cache.get(pkg)
        assert len(first.modules) == 1

        (pkg / "new_mod.py").write_text(
            '"""New."""\ndef greet() -> str:\n    return "hello"'
        )
        second = cache.get(pkg)
        assert second is not first
        module_names = [m.path.stem for m in second.modules]
        assert "new_mod" in module_names

    @pytest.mark.integration
    def test_clear_cache_full_reset(self, tmp_path: Path) -> None:
        """clear() forces full re-parse on next call."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')

        cache = PackageCache()
        first = cache.get(pkg)
        cache.clear()
        second = cache.get(pkg)
        assert second is not first
        assert first.name == second.name


# ─── Content modification invalidation ──────────────────────────────────────


class TestPackageCacheMtimeInvalidation:
    """Cache invalidates when .py file content is modified."""

    @pytest.mark.integration
    def test_cache_invalidation_on_modify(self, tmp_path: Path) -> None:
        """Modifying a .py file's content → cache invalidates, re-parses."""
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

        time.sleep(0.05)
        mod.write_text(
            '"""Mod."""\ndef goodbye() -> str:\n    """Goodbye."""\n    return "bye"'
        )

        second = cache.get(pkg)
        assert second is not first
        func_names = [f.name for m in second.modules for f in m.functions]
        assert "goodbye" in func_names
        assert "hello" not in func_names


# ─── Call-site caching ──────────────────────────────────────────────────────


class TestPackageCacheGetCalls:
    """Tests for get_calls() — cached call-site extraction."""

    @pytest.mark.integration
    def test_get_calls_contains_expected_modules(self, tmp_path: Path) -> None:
        """get_calls() returns call-sites keyed by module name."""
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
        assert "pkg.cli" in calls or "cli" in calls
        all_symbols = [c.symbol for cs in calls.values() for c in cs]
        assert "greet" in all_symbols

    @pytest.mark.integration
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
        assert first is second

    @pytest.mark.integration
    def test_get_calls_invalidation_on_modify(self, tmp_path: Path) -> None:
        """Modifying a file evicts both PackageInfo and call-sites."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""')
        mod = pkg / "mod.py"
        mod.write_text('"""Mod."""\ndef setup() -> None:\n    """Setup."""\n    foo()')

        cache = PackageCache()
        first_calls = cache.get_calls(pkg)
        all_symbols = [c.symbol for calls in first_calls.values() for c in calls]
        assert "foo" in all_symbols

        time.sleep(0.05)
        mod.write_text('"""Mod."""\ndef setup() -> None:\n    """Setup."""\n    bar()')

        second_calls = cache.get_calls(pkg)
        assert second_calls is not first_calls
        all_symbols = [c.symbol for calls in second_calls.values() for c in calls]
        assert "bar" in all_symbols
        assert "foo" not in all_symbols
