"""Integration tests for PackageCache — filesystem invalidation and real I/O.

Tests that exercise cache behavior with real file creation, deletion, and
modification via tmp_path. Covers the ``PackageCache`` public API only.

Split from ``test_cache_mod__package_cache.py`` (the TOCTOU scenarios that
also reach the ``cache_mod`` module alias stay in the original file).
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.cache import CacheLimits, PackageCache

# ─── Path handling ─────────────────────────────────────────────


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


# ─── Edge cases ────────────────────────────────────────────────


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


# ─── Filesystem change invalidation (AXM-166) ────────────────────────


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


# ─── Content modification invalidation ───────────────────────────────


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


# ─── Call-site caching ──────────────────────────────────────────


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


# ─── Cache-hit semantics (AXM-1885) ─────────────────────────────────────────


class TestPackageCacheHit:
    """Unchanged files return the same cached PackageInfo instance."""

    @pytest.mark.integration
    def test_get_returns_cached_on_unchanged_files(self, tmp_path: Path) -> None:
        """AC3: unchanged files → second get is a cache hit (same object).

        The public ``get`` API and cache-hit semantics are unchanged by the
        fingerprint reorder: no filesystem mutation means the second call
        returns the exact same ``PackageInfo`` instance.
        """
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        (pkg / "mod.py").write_text('"""Mod."""\ndef hello() -> str:\n    return "hi"')

        cache = PackageCache()
        first = cache.get(pkg)
        second = cache.get(pkg)
        assert first is second


# ─── Memory bounds: dead paths, idle TTL, weight ceiling ───────────────────


class _FakeClock:
    """Manually advanced monotonic clock (no sleeps)."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _make_pkgs(tmp_path: Path, *names: str) -> list[Path]:
    """Create one tiny package per name, each with a call-site."""
    pkgs = []
    for name in names:
        pkg = tmp_path / name
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            f'"""{name}."""\ndef run() -> None:\n    """Run."""\n    helper()\n'
        )
        pkgs.append(pkg)
    return pkgs


@contextmanager
def _spy_and_weigh(weight: int | None = None) -> Iterator[MagicMock]:
    """Spy on parses; optionally pin every package's estimated weight."""
    with patch("axm_ast.core.cache.analyze_package", wraps=analyze_package) as spy:
        if weight is None:
            yield spy
        else:
            with patch("axm_ast.core.cache._package_weight", return_value=weight):
                yield spy


class TestPackageCacheDeadPath:
    """Entries whose directory vanished are evicted (deleted worktrees)."""

    @pytest.mark.integration
    def test_sweep_evicts_deleted_directory(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        cache = PackageCache(CacheLimits(sweep_interval_seconds=0))
        cache.get(a)
        cache.get(b)

        shutil.rmtree(a)
        cache.get(b)

        stats = cache.stats()
        assert stats.entries == 1
        assert stats.evicted_dead == 1

    @pytest.mark.integration
    def test_access_to_deleted_directory_behaves_like_miss(
        self, tmp_path: Path
    ) -> None:
        (a,) = _make_pkgs(tmp_path, "a")
        cache = PackageCache()
        cache.get(a)

        shutil.rmtree(a)
        with pytest.raises(ValueError):
            cache.get(a)

        stats = cache.stats()
        assert stats.entries == 0
        assert stats.evicted_dead == 1


class TestPackageCacheWeightBound:
    """LRU eviction over the estimated-weight ceiling."""

    @pytest.mark.integration
    def test_over_ceiling_evicts_least_recently_used(self, tmp_path: Path) -> None:
        a, b, c, d = _make_pkgs(tmp_path, "a", "b", "c", "d")
        cache = PackageCache(CacheLimits(max_weight_bytes=250))
        with _spy_and_weigh(weight=100) as spy:
            cache.get(a)
            cache.get(b)
            cache.get(c)  # 300 > 250 -> evict a (LRU)
            cache.get(b)  # hit, b becomes most recent
            cache.get(d)  # evict c, not b
            assert spy.call_count == 4
            cache.get(b)
            cache.get(d)
            assert spy.call_count == 4
            cache.get(a)
            assert spy.call_count == 5

        assert cache.stats().evicted_weight == 3

    @pytest.mark.integration
    def test_oversized_entry_stays_cached(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        cache = PackageCache(CacheLimits(max_weight_bytes=50))
        with _spy_and_weigh(weight=100) as spy:
            first = cache.get(a)
            assert cache.get(a) is first
            assert spy.call_count == 1
            second = cache.get(b)
            assert cache.get(b) is second
            assert spy.call_count == 2

        stats = cache.stats()
        assert stats.entries == 1
        assert stats.evicted_weight == 1

    @pytest.mark.integration
    def test_disabled_ceiling_never_evicts(self, tmp_path: Path) -> None:
        pkgs = _make_pkgs(tmp_path, "a", "b", "c")
        cache = PackageCache(CacheLimits(max_weight_bytes=None))
        with _spy_and_weigh(weight=10**12):
            for pkg in pkgs:
                cache.get(pkg)
        assert cache.stats().entries == 3

    @pytest.mark.integration
    def test_weight_grows_with_calls_and_index(self, tmp_path: Path) -> None:
        (a,) = _make_pkgs(tmp_path, "a")
        cache = PackageCache()
        cache.get(a)
        package_only = cache.stats().weight_bytes
        cache.get_calls(a)
        with_calls = cache.stats().weight_bytes
        cache.get_call_index(a)
        with_index = cache.stats().weight_bytes
        assert 0 < package_only < with_calls < with_index


class TestPackageCacheIdleTtl:
    """Idle entries are evicted by the throttled sweep."""

    @pytest.mark.integration
    def test_idle_entry_evicted_after_ttl(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        clock = _FakeClock()
        cache = PackageCache(
            CacheLimits(ttl_seconds=10, sweep_interval_seconds=0), clock=clock
        )
        cache.get(a)
        clock.now = 5
        cache.get(b)
        clock.now = 12  # a idle 12 s, b idle 7 s
        cache.get(b)

        stats = cache.stats()
        assert stats.entries == 1
        assert stats.evicted_ttl == 1
        with _spy_and_weigh() as spy:
            cache.get(b)
            assert spy.call_count == 0

    @pytest.mark.integration
    def test_accessed_entry_survives_past_ttl(self, tmp_path: Path) -> None:
        """The key being accessed is spared by the sweep, not re-parsed."""
        (a,) = _make_pkgs(tmp_path, "a")
        clock = _FakeClock()
        cache = PackageCache(
            CacheLimits(ttl_seconds=10, sweep_interval_seconds=0), clock=clock
        )
        first = cache.get(a)
        clock.now = 1_000
        assert cache.get(a) is first
        assert cache.stats().evicted_ttl == 0

    @pytest.mark.integration
    def test_sweep_is_throttled(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        clock = _FakeClock()
        cache = PackageCache(
            CacheLimits(ttl_seconds=10, sweep_interval_seconds=60), clock=clock
        )
        cache.get(a)
        clock.now = 30
        cache.get(b)  # a idle 30 s but no sweep before t=60
        assert cache.stats().entries == 2
        clock.now = 60
        cache.get(b)
        assert cache.stats().evicted_ttl == 1

    @pytest.mark.integration
    def test_ttl_none_disables_idle_eviction(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        clock = _FakeClock()
        cache = PackageCache(
            CacheLimits(ttl_seconds=None, sweep_interval_seconds=0), clock=clock
        )
        cache.get(a)
        clock.now = 10**9
        cache.get(b)
        assert cache.stats().entries == 2


class TestPackageCacheSharedLifecycle:
    """Call-sites and index live and die with their package."""

    @pytest.mark.integration
    def test_calls_and_index_evicted_with_package(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        clock = _FakeClock()
        cache = PackageCache(
            CacheLimits(ttl_seconds=10, sweep_interval_seconds=0), clock=clock
        )
        calls = cache.get_calls(a)
        index = cache.get_call_index(a)
        clock.now = 11
        cache.get(b)  # sweep evicts a's whole entry

        assert cache.stats().entries == 1
        new_calls = cache.get_calls(a)
        new_index = cache.get_call_index(a)
        assert new_calls is not calls
        assert new_index is not index
        assert new_calls == calls
        assert new_index == index
        assert "helper" in new_index

    @pytest.mark.integration
    def test_stale_fingerprint_reparses_and_rebuilds_calls(
        self, tmp_path: Path
    ) -> None:
        (a,) = _make_pkgs(tmp_path, "a")
        cache = PackageCache()
        first = cache.get(a)
        index = cache.get_call_index(a)

        init = a / "__init__.py"
        init.write_text('"""a."""\ndef run() -> None:\n    """Run."""\n    other()\n')
        st = init.stat()
        os.utime(init, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

        assert cache.get(a) is not first
        new_index = cache.get_call_index(a)
        assert new_index is not index
        assert "other" in new_index
        assert "helper" not in new_index
        stats = cache.stats()
        assert stats.evicted_stale == 1
        assert stats.misses == 2


class TestPackageCacheStats:
    """Read-only counters for diagnostics."""

    @pytest.mark.integration
    def test_hits_and_misses_counted(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        cache = PackageCache()
        cache.get(a)
        cache.get(a)
        cache.get(a)
        cache.get(b)

        stats = cache.stats()
        assert (stats.hits, stats.misses, stats.entries) == (2, 2, 2)
        assert stats.max_weight_bytes == CacheLimits().max_weight_bytes
        assert stats.ttl_seconds == CacheLimits().ttl_seconds

    @pytest.mark.integration
    def test_clear_resets_entries_weight_and_counters(self, tmp_path: Path) -> None:
        a, b = _make_pkgs(tmp_path, "a", "b")
        cache = PackageCache(CacheLimits(max_weight_bytes=1))
        cache.get_call_index(a)
        cache.get(a)
        cache.get(b)
        assert cache.stats().evicted_weight == 1

        cache.clear()

        stats = cache.stats()
        assert stats.entries == 0
        assert stats.weight_bytes == 0
        assert (stats.hits, stats.misses) == (0, 0)
        assert (
            stats.evicted_stale,
            stats.evicted_dead,
            stats.evicted_ttl,
            stats.evicted_weight,
        ) == (0, 0, 0, 0)


class TestPackageCacheConcurrency:
    """Thread-safety smoke test under constant eviction pressure."""

    @pytest.mark.integration
    def test_concurrent_access_with_evictions(self, tmp_path: Path) -> None:
        pkgs = _make_pkgs(tmp_path, "a", "b", "c")
        cache = PackageCache(CacheLimits(max_weight_bytes=1, sweep_interval_seconds=0))

        def work(i: int) -> list[str]:
            return sorted(cache.get_call_index(pkgs[i % 3]))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(work, range(60)))

        assert all(result == ["helper"] for result in results)
        assert cache.stats().entries >= 1
