"""Integration tests for PackageCache TOCTOU fingerprint capture (AXM-1885).

Exercises the public ``PackageCache.get`` API with real filesystem I/O. The
fingerprint must be captured *before* ``analyze_package`` runs, so that a file
modified during analysis is detected as stale on the next ``get`` instead of
being baked into a permanently-fresh entry.

Rule: never test the ``_file_fingerprint`` / ``analyze_package`` private/internal
helpers directly — every scenario goes through ``PackageCache.get``.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import axm_ast.core.cache as cache_mod
from axm_ast.core.cache import PackageCache


@pytest.mark.integration
def test_get_invalidates_after_file_modification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: a file mutated *during* analyze_package is invalidated on next get.

    This reproduces the TOCTOU window: if the fingerprint were captured *after*
    ``analyze_package``, the modification done while analysis runs would be
    baked into the stored fingerprint, so the next ``get`` would see
    ``current_fp == cached_fp`` and never reparse — permanent staleness.

    Capturing the fingerprint *before* analysis means the first stored
    fingerprint predates the mutation, so the second ``get`` detects the change
    and recomputes a ``PackageInfo`` reflecting the new content.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Init."""')
    mod = pkg / "mod.py"
    mod.write_text('"""Mod."""\ndef hello() -> str:\n    """Hello."""\n    return "hi"')

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


@pytest.mark.integration
def test_get_returns_cached_on_unchanged_files(tmp_path: Path) -> None:
    """AC3: unchanged files → second get is a cache hit (same object).

    The public ``get`` API and cache-hit semantics are unchanged by the
    fingerprint reorder: no filesystem mutation means the second call returns
    the exact same ``PackageInfo`` instance.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Init."""')
    (pkg / "mod.py").write_text('"""Mod."""\ndef hello() -> str:\n    return "hi"')

    cache = PackageCache()
    first = cache.get(pkg)
    second = cache.get(pkg)
    assert first is second
