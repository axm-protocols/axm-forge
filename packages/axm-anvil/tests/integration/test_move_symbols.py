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
from tests.integration._helpers import _write_workspace

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


def test_conditional_guard_spliced_after_target_docstring(tmp_path: Path) -> None:
    """P1-2: a moved symbol's conditional-import guard is inserted *after* the
    target module docstring, preserving ``module.__doc__``.

    Before the fix the ``try/except`` guard was prepended at body position 0,
    demoting the docstring to an ordinary string statement (``__doc__`` -> None).
    """
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'tmp_pkg'\nversion = '0.1.0'\n"
    )
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "try:\n"
        "    import ujson as json\n"
        "except ImportError:\n"
        "    import json\n"
        "\n"
        "\n"
        "def dump(obj: object) -> str:\n"
        "    return json.dumps(obj)\n"
    )
    target.write_text('"""Target module docstring."""\n')

    move_symbols(source, target, ["dump"], dry_run=False, workspace_root=tmp_path)

    rendered = target.read_text()
    # The docstring must remain the very first statement of the module.
    assert rendered.lstrip().startswith('"""Target module docstring."""')
    # The guard landed after the docstring, not before it.
    doc_idx = rendered.index('"""Target module docstring."""')
    guard_idx = rendered.index("import ujson")
    assert doc_idx < guard_idx
    # And ``module.__doc__`` is still parseable as the docstring.
    namespace: dict[str, object] = {}
    exec(compile(rendered, str(target), "exec"), namespace)  # noqa: S102
    assert namespace["__doc__"] == "Target module docstring."


def test_cross_package_caller_import_is_rewritten(tmp_path: Path) -> None:
    """P0: a move in a real ``packages/pkg/src/pkg`` monorepo actually rewrites
    the *consumer package's* import — not a silent no-op reporting success.

    ``pkg_b/caller.py`` imports ``from pkg_a.mod import foo``; after moving
    ``foo`` from ``pkg_a/mod.py`` to ``pkg_a/other.py`` the caller must import
    from ``pkg_a.other`` — asserting the consumer file content changed.
    """
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    mod = pkg_a / "mod.py"
    other = pkg_a / "other.py"
    caller = pkg_b / "caller.py"
    mod.write_text("def foo():\n    return 1\n")
    other.write_text("")
    caller.write_text(
        "from pkg_a.mod import foo\n\n\ndef use() -> int:\n    return foo()\n"
    )
    caller_before = caller.read_text()

    plan = move_symbols(mod, other, ["foo"], workspace_root=tmp_path)

    caller_after = caller.read_text()
    assert caller_after != caller_before, "consumer file was not rewritten"
    assert "from pkg_a.other import foo" in caller_after
    assert "from pkg_a.mod import foo" not in caller_after
    assert [r.file for r in plan.callers_updated] == [
        "packages/pkg_b/src/pkg_b/caller.py"
    ]


def test_cross_package_module_import_caller_is_rewritten(tmp_path: Path) -> None:
    """P0: a consumer using ``import pkg_a.mod`` + ``pkg_a.mod.Foo`` is
    redirected to ``pkg_a.other`` in the monorepo layout."""
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    mod = pkg_a / "mod.py"
    other = pkg_a / "other.py"
    caller = pkg_b / "caller.py"
    mod.write_text("class Foo:\n    pass\n")
    other.write_text("")
    caller.write_text(
        "import pkg_a.mod\n\n\ndef use() -> object:\n    return pkg_a.mod.Foo()\n"
    )
    caller_before = caller.read_text()

    move_symbols(mod, other, ["Foo"], workspace_root=tmp_path)

    caller_after = caller.read_text()
    assert caller_after != caller_before
    assert "pkg_a.other.Foo()" in caller_after


def test_cross_package_aliased_import_kept_when_used_as_bare_name(
    tmp_path: Path,
) -> None:
    """P1-3: an ``import pkg_a.mod as om`` consumer that also uses ``om`` as a
    bare value (``registry = om``) keeps its import after the move — dropping it
    would leave ``registry = om`` unbound (NameError).
    """
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    mod = pkg_a / "mod.py"
    other = pkg_a / "other.py"
    caller = pkg_b / "caller.py"
    mod.write_text("class Foo:\n    pass\n")
    other.write_text("")
    caller.write_text(
        "import pkg_a.mod as om\n\n\n"
        "def use() -> object:\n    return om.Foo()\n\n\n"
        "registry = om\n"
    )

    move_symbols(mod, other, ["Foo"], workspace_root=tmp_path)

    caller_after = caller.read_text()
    assert "pkg_a.other.Foo()" in caller_after
    # The bare value reference survives, so the alias import must be kept.
    assert "registry = om" in caller_after
    assert "import pkg_a.mod as om" in caller_after


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
