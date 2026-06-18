"""Integration tests for the data-driven package discovery walk (AC4).

Exercises ``discover_package_roots`` + ``extract_monorepo`` against a real
workspace tree on disk: the ``<ws>/packages/<pkg>`` convention, the flat
``other/<pkg>`` layout, and the automatic pickup of newly-added packages.
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
    config_dir = home / ".axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root}"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))


def test_discovers_packages_and_other_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: both ``<ws>/packages/<pkg>`` and flat ``other/<pkg>`` are walked."""
    ws = tmp_path / "workspace"
    home = tmp_path / "home"
    home.mkdir()

    # `<ws>/<child>/packages/<pkg>` convention.
    _src_package(
        ws / "axm-thing" / "packages",
        "pkg-one",
        'def alpha() -> None:\n    """A."""\n',
    )
    # Flat `other/<pkg>` layout.
    _src_package(ws / "other", "flat-pkg", 'def beta() -> None:\n    """B."""\n')

    _point_scope_at(home, monkeypatch, ws)

    roots = discover_package_roots()
    names = {r.name for r in roots}

    assert "pkg-one" in names
    assert "flat-pkg" in names
    # The list is sorted and de-duplicated.
    assert roots == sorted(set(roots))


def test_extract_monorepo_concatenates_symbols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """extract_monorepo returns the concatenated corpus across packages."""
    ws = tmp_path / "workspace"
    home = tmp_path / "home"
    home.mkdir()

    _src_package(
        ws / "axm-a" / "packages",
        "pkg-a",
        'def alpha() -> None:\n    """Alpha doc."""\n',
    )
    _src_package(
        ws / "axm-b" / "packages",
        "pkg-b",
        'def beta() -> None:\n    """Beta doc."""\n',
    )

    _point_scope_at(home, monkeypatch, ws)

    symbols = extract_monorepo()
    names = {s["name"] for s in symbols}

    assert {"alpha", "beta"} <= names
    # Every symbol carries an embed_text (the corpus is ready for embedding).
    assert all(s["embed_text"] for s in symbols)
