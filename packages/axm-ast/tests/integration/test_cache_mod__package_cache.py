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
from axm_ast.core.cache import PackageCache

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
