"""Unit tests for the node workspace (monorepo) gold-standard checks."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.workspace import (
    check_packages_layout,
    check_workspaces_declared,
    check_workspaces_versions_consistent,
)


def _ws_root(tmp_path: Path) -> Path:
    """Create a workspace root with a members directory."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "root", "workspaces": ["packages/*"]})
    )
    (tmp_path / "packages").mkdir()
    return tmp_path


def _member(root: Path, name: str, *, version: str | None = "0.1.0") -> None:
    """Create a workspace member with an optional version."""
    d = root / "packages" / name
    d.mkdir()
    data: dict[str, object] = {"name": name}
    if version is not None:
        data["version"] = version
    (d / "package.json").write_text(json.dumps(data))


def test_single_package_is_not_applicable(tmp_path: Path) -> None:
    """On a single-package project the workspace checks auto-pass."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "solo"}))
    assert check_workspaces_declared(tmp_path).passed is True
    assert check_packages_layout(tmp_path).passed is True


def test_packages_layout_detected(tmp_path: Path) -> None:
    """A workspace with packages/* members passes the layout check."""
    root = _ws_root(tmp_path)
    _member(root, "a")
    assert check_packages_layout(root).passed is True


def test_packages_layout_missing_fails(tmp_path: Path) -> None:
    """A workspace root with no members fails the layout check."""
    root = _ws_root(tmp_path)  # packages/ exists but empty
    assert check_packages_layout(root).passed is False


def test_versions_consistent_flags_unversioned_member(tmp_path: Path) -> None:
    """A member without a version is flagged."""
    root = _ws_root(tmp_path)
    _member(root, "ok")
    _member(root, "bad", version=None)
    result = check_workspaces_versions_consistent(root)
    assert result.passed is False
    assert "bad" in result.details[0]


def test_versions_consistent_passes_when_all_versioned(tmp_path: Path) -> None:
    """All members versioned passes."""
    root = _ws_root(tmp_path)
    _member(root, "a")
    _member(root, "b")
    assert check_workspaces_versions_consistent(root).passed is True
