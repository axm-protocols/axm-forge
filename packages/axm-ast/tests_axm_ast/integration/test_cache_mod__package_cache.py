"""TOCTOU fingerprint-capture tests for PackageCache (AXM-1885).

These scenarios reach the ``cache_mod`` module alias to monkeypatch
``analyze_package`` and reproduce the time-of-check/time-of-use window. The
pure ``PackageCache`` filesystem-invalidation tests live in
``test_package_cache.py``.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import axm_ast.core.cache as cache_mod
from axm_ast.core.analyzer import fingerprint_source_tree
from axm_ast.core.cache import PackageCache, clear_cache, get_package

# ─── TOCTOU fingerprint capture (AXM-1885) ──────────────────────────────────


class TestPackageCacheToctou:
    """Fingerprint must be captured *before* ``analyze_package`` runs.

    A file modified during analysis must be detected as stale on the next
    ``get`` instead of being baked into a permanently-fresh entry. Every
    scenario goes through the public ``PackageCache.get`` API — never the
    ``_file_fingerprint`` / ``analyze_package`` private/internal helpers.
    """

    @pytest.mark.integration
    def test_get_invalidates_after_file_modification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC2: a file mutated *during* analyze_package is invalidated on next get.

        This reproduces the TOCTOU window: if the fingerprint were captured
        *after* ``analyze_package``, the modification done while analysis runs
        would be baked into the stored fingerprint, so the next ``get`` would
        see ``current_fp == cached_fp`` and never reparse — permanent staleness.

        Capturing the fingerprint *before* analysis means the first stored
        fingerprint predates the mutation, so the second ``get`` detects the
        change and recomputes a ``PackageInfo`` reflecting the new content.
        """
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Init."""')
        mod = pkg / "mod.py"
        mod.write_text(
            '"""Mod."""\ndef hello() -> str:\n    """Hello."""\n    return "hi"'
        )

        real_analyze = cache_mod.analyze_package
        state = {"mutated": False}

        def analyze_then_mutate(key: Path) -> object:
            # Run the real analysis, then mutate the source on disk *during* the
            # call window — exactly the race the fix narrows. Mutate once so the
            # recompute (second get) sees a stable file.
            result = real_analyze(key)
            if not state["mutated"]:
                time.sleep(0.05)
                mod.write_text(
                    '"""Mod."""\ndef goodbye() -> str:\n'
                    '    """Goodbye."""\n    return "bye"'
                )
                state["mutated"] = True
            return result

        monkeypatch.setattr(cache_mod, "analyze_package", analyze_then_mutate)

        cache = PackageCache()
        first = cache.get(pkg)
        assert any(f.name == "hello" for m in first.modules for f in m.functions)

        second = cache.get(pkg)
        assert second is not first
        func_names = [f.name for m in second.modules for f in m.functions]
        assert "goodbye" in func_names
        assert "hello" not in func_names


def _make_package_with_build_module(
    tmp_path: Path, module_name: str, source: str
) -> Path:
    package = tmp_path / "pkg"
    build = package / "build"
    build.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Package."""\n')
    (build / "__init__.py").write_text('"""Build package."""\n')
    (build / f"{module_name}.py").write_text(source)
    return package


def _module_paths(package_info: object) -> set[str]:
    return {
        module.path.relative_to(package_info.root).as_posix()
        for module in package_info.modules
    }


@pytest.mark.integration
def test_get_package_invalidates_when_build_package_module_is_added(
    tmp_path: Path,
) -> None:
    """AC2: adding a module under a marked build package refreshes analysis."""
    clear_cache()
    package = _make_package_with_build_module(
        tmp_path,
        "existing",
        "EXISTING = 1\n",
    )
    before_fingerprint = fingerprint_source_tree(package)
    before = get_package(package)

    (package / "build" / "added.py").write_text("ADDED = 1\n")

    after_fingerprint = fingerprint_source_tree(package)
    after = get_package(package)

    assert after_fingerprint != before_fingerprint
    assert after is not before
    assert "build/added.py" in _module_paths(after)


@pytest.mark.integration
def test_get_package_invalidates_when_build_package_module_is_modified(
    tmp_path: Path,
) -> None:
    """AC3: modifying a module under a marked build package refreshes metadata."""
    clear_cache()
    package = _make_package_with_build_module(
        tmp_path,
        "changing",
        "def old_symbol() -> str:\n    return 'old'\n",
    )
    module = package / "build" / "changing.py"
    before_fingerprint = fingerprint_source_tree(package)
    before = get_package(package)

    time.sleep(0.05)
    module.write_text("def replacement_symbol() -> str:\n    return 'replacement'\n")

    after_fingerprint = fingerprint_source_tree(package)
    after = get_package(package)
    function_names = {
        function.name
        for parsed_module in after.modules
        for function in parsed_module.functions
    }

    assert after_fingerprint != before_fingerprint
    assert after is not before
    assert "replacement_symbol" in function_names
    assert "old_symbol" not in function_names


@pytest.mark.integration
def test_get_package_invalidates_when_build_package_module_is_deleted(
    tmp_path: Path,
) -> None:
    """AC4: deleting a module under a marked build package refreshes analysis."""
    clear_cache()
    package = _make_package_with_build_module(
        tmp_path,
        "removed",
        "REMOVED = 1\n",
    )
    removed = package / "build" / "removed.py"
    before_fingerprint = fingerprint_source_tree(package)
    before = get_package(package)
    assert "build/removed.py" in _module_paths(before)

    removed.unlink()

    after_fingerprint = fingerprint_source_tree(package)
    after = get_package(package)

    assert after_fingerprint != before_fingerprint
    assert after is not before
    assert "build/removed.py" not in _module_paths(after)
