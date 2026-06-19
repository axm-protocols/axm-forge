"""Integration tests for the data-driven package discovery walk.

Exercises ``discover_package_roots`` + ``extract_monorepo`` against a real
workspace tree on disk that reproduces the genuine AXM convention: the
scope (``~/axm/echo.toml``) lists *workspace roots directly*, and packages
live at ``<workspace_root>/packages/<pkg>`` (AXM-2184: the buggy code looked
one level too deep). Also covers the flat ``other/<pkg>`` layout, rejection
of doc dirs / stray ``*.py`` directories, and the automatic pickup of
newly-added packages.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_echo.corpus import discover_package_roots, extract_monorepo

# A cohesive package-discovery scenario spanning discover_package_roots +
# extract_monorepo on a real workspace tree; intentionally more than one
# canonical symbol tuple.
pytestmark = [pytest.mark.integration, pytest.mark.scenario_name_ok]


def _src_package(parent: Path, name: str, body: str) -> Path:
    """Write a ``<parent>/<name>/src/<name>/mod.py`` package; return its root."""
    root = parent / name
    pkg = root / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return root


def _point_scope_at(home: Path, monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make ``load_scope`` read a config whose only workspace root is ``root``."""
    config_dir = home / "axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root}"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))


def test_workspace_packages_layout_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC3: packages under ``<ws>/packages/<pkg>`` are discovered.

    Reproduces the genuine convention where the scope lists the workspace
    root directly (e.g. ``axm-forge``) and packages live one level below in
    ``packages/``.
    """
    ws = tmp_path / "axm-forge"
    home = tmp_path / "home"
    home.mkdir()

    for name in ("axm-ast", "axm-audit", "axm-echo"):
        sym = name.replace("-", "_")
        _src_package(ws / "packages", name, f'def s_{sym}() -> None:\n    """Doc."""\n')

    _point_scope_at(home, monkeypatch, ws)

    roots = discover_package_roots()
    pkgs = ws / "packages"
    expected = {pkgs / "axm-ast", pkgs / "axm-audit", pkgs / "axm-echo"}

    assert expected.issubset(set(roots))
    assert len(roots) == 3
    # The list is sorted and de-duplicated.
    assert roots == sorted(set(roots))


def test_docs_dir_not_a_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2, AC4: a ``docs/`` dir with a stray ``*.py`` is not a package."""
    ws = tmp_path / "axm-forge"
    home = tmp_path / "home"
    home.mkdir()

    _src_package(ws / "packages", "axm-ast", 'def alpha() -> None:\n    """A."""\n')
    docs = ws / "packages" / "docs"
    docs.mkdir(parents=True)
    (docs / "gen_ref_pages.py").write_text("# doc generator\n", encoding="utf-8")

    _point_scope_at(home, monkeypatch, ws)

    roots = discover_package_roots()

    assert (ws / "packages" / "axm-ast") in roots
    assert docs not in roots


def test_other_flat_layout_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: the flat ``other/<pkg>`` layout remains discoverable."""
    ws = tmp_path / "axm-workspaces"
    home = tmp_path / "home"
    home.mkdir()

    _src_package(ws / "other", "axm-imessage", 'def beta() -> None:\n    """B."""\n')
    _src_package(ws / "other", "gitagent", 'def gamma() -> None:\n    """G."""\n')

    _point_scope_at(home, monkeypatch, ws)

    roots = discover_package_roots()

    assert (ws / "other" / "axm-imessage") in roots
    assert (ws / "other" / "gitagent") in roots


def test_pyproject_marks_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a dir is a package iff it has ``src/`` or ``pyproject.toml``.

    A dir holding only a stray ``*.py`` (no ``src/``, no ``pyproject.toml``)
    must NOT be discovered. Verified through the public
    ``discover_package_roots`` boundary, not the private helper.
    """
    ws = tmp_path / "axm-workspaces"
    home = tmp_path / "home"
    home.mkdir()

    real = ws / "other" / "real-pkg"
    real.mkdir(parents=True)
    (real / "pyproject.toml").write_text('[project]\nname = "real"\n', encoding="utf-8")
    fake = ws / "other" / "fake-pkg"
    fake.mkdir()
    (fake / "helper.py").write_text("x = 1\n", encoding="utf-8")

    _point_scope_at(home, monkeypatch, ws)

    roots = discover_package_roots()

    assert real in roots
    assert fake not in roots


def test_extract_monorepo_concatenates_symbols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """extract_monorepo returns the concatenated corpus across packages."""
    ws = tmp_path / "axm-forge"
    home = tmp_path / "home"
    home.mkdir()

    _src_package(
        ws / "packages", "pkg-a", 'def alpha() -> None:\n    """Alpha doc."""\n'
    )
    _src_package(ws / "packages", "pkg-b", 'def beta() -> None:\n    """Beta doc."""\n')

    _point_scope_at(home, monkeypatch, ws)

    symbols = extract_monorepo()
    names = {s["name"] for s in symbols}

    assert {"alpha", "beta"} <= names
    # Every symbol carries an embed_text (the corpus is ready for embedding).
    assert all(s["embed_text"] for s in symbols)
