"""Integration tests for reverse-import detection over a real package tree.

Exercises ``analyze_impact(..., include_module_importers=True)`` against an
on-disk package that re-exports the edited symbol's module through a shim,
asserting that a file importing the shim is reported as a module-level
importer (AC1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.impact import analyze_impact


def _write_shim_pkg(root: Path) -> Path:
    """Write a package where ``c`` imports a shim re-exporting ``m``.

    Layout::

        mypkg/m.py     -> defines ``target``
        mypkg/shim.py  -> ``from mypkg.m import target`` (re-export shim)
        mypkg/c.py     -> ``import mypkg.shim`` (imports the shim, not target)

    ``c`` reaches ``target``'s module only transitively, through the shim —
    a dependency a symbol-level call-graph traversal cannot see.
    """
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "m.py").write_text("def target() -> int:\n    return 1\n")
    (pkg / "shim.py").write_text("from mypkg.m import target\n\n__all__ = ['target']\n")
    (pkg / "c.py").write_text("import mypkg.shim\n")
    return pkg


@pytest.mark.integration
def test_reverse_import_resolves_shim_importers(tmp_path: Path) -> None:
    """AC1: opt-in resolves shim/re-export importers over a real tree."""
    pkg = _write_shim_pkg(tmp_path)

    result = analyze_impact(pkg, "target", include_module_importers=True)

    importers = result["module_level_importers"]
    # The file importing the shim is surfaced as a module-level importer.
    assert "c" in importers
    # The shim itself (a direct importer of the module) is surfaced too.
    assert "shim" in importers
