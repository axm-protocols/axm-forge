"""Integration tests for :func:`axm_anvil.core.move.move_symbols`.

Groups the move-pipeline scenarios that exercise only ``move_symbols`` (the
FILE_NAMING canonical tuple): project-root / pyproject fallback resolution, and
workspace-graph caller rewriting (AC3 of AXM-2136 — anvil's workspace-graph
imports run through the public ``axm_ast`` surface and must not regress the
cross-module move).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration

_SOURCE = "def kept():\n    return 1\n\n\ndef moved():\n    return 2\n"
_TARGET = ""


def _seed(directory: Path, *, with_pyproject: bool) -> tuple[Path, Path]:
    """Lay out a movable source/target pair, optionally rooted by a pyproject."""
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source.py"
    target = directory / "target.py"
    source.write_text(_SOURCE)
    target.write_text(_TARGET)
    if with_pyproject:
        (directory / "pyproject.toml").write_text(
            "[project]\nname = 'tmp_pkg'\nversion = '0.1.0'\n"
        )
    return source, target


def test_move_resolves_project_root(tmp_path: Path) -> None:
    """AC1, AC2: with ``workspace_root=None`` the move falls back to the project
    root resolution that ``_find_workspace_root`` provided — the first ancestor
    carrying any ``pyproject.toml`` (here ``tmp_path``).

    Exercised through the public ``move_symbols`` pipeline: the package code
    sits under ``pkg/`` while ``tmp_path`` holds the only ``pyproject.toml``, so
    a correct project-root resolution anchors relative paths on ``tmp_path``
    and the move succeeds (a None/wrong root would raise or misplace).
    """
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'tmp_pkg'\nversion = '0.1.0'\n"
    )
    source, target = _seed(tmp_path / "pkg", with_pyproject=False)

    plan = move_symbols(source, target, ["moved"], dry_run=False)

    assert "moved" in plan.moved_names
    assert "moved" in target.read_text()
    assert "moved" not in source.read_text()


def test_fallback_when_no_pyproject(tmp_path: Path) -> None:
    """AC2: with no ``pyproject.toml`` anywhere and ``workspace_root=None`` the
    root resolution falls back to the starting directory instead of raising or
    propagating ``None``.

    Exercised through the public ``move_symbols`` pipeline: the legacy
    ``_find_workspace_root`` always returned a ``Path`` (start dir fallback), so
    the move must complete without an exception even outside any project.
    """
    source, target = _seed(tmp_path / "loose", with_pyproject=False)

    plan = move_symbols(source, target, ["moved"], dry_run=False)

    assert "moved" in plan.moved_names
    assert "moved" in target.read_text()
    assert "moved" not in source.read_text()


def test_move_still_resolves_workspace_graph(workspace: Path) -> None:
    """AC3: a cross-module move updates callers via the workspace graph."""
    pkg = workspace / "src" / "pkg"
    old = pkg / "old.py"
    new = pkg / "new.py"
    old.write_text("def Foo():\n    return 1\n")
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo\n\nFoo()\n")

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    # The workspace graph was resolved: the caller import was rewritten to the
    # new module (proof the move pipeline still walks the workspace module
    # graph through the public axm_ast surface).
    assert "Foo" in plan.moved_names
    caller_text = caller.read_text()
    assert "from pkg.new import Foo" in caller_text
    assert "from pkg.old import Foo" not in caller_text
