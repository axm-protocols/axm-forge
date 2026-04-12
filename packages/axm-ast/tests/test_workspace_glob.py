from __future__ import annotations

import logging
from pathlib import Path

import pytest

from axm_ast.core.workspace import (
    _build_package_edges,
    _expand_workspace_members,
    _parse_workspace_members,
    analyze_workspace,
)

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_parse_workspace_members_glob() -> None:
    """_parse_workspace_members returns raw glob strings unchanged."""
    text = '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    result = _parse_workspace_members(text)
    assert result == ["packages/*"]


def test_expand_members_glob(tmp_path: Path) -> None:
    """Glob patterns are expanded to matching directory paths."""
    (tmp_path / "packages" / "pkg-a").mkdir(parents=True)
    (tmp_path / "packages" / "pkg-b").mkdir(parents=True)
    result = _expand_workspace_members(tmp_path, ["packages/*"])
    assert sorted(result) == ["packages/pkg-a", "packages/pkg-b"]


def test_expand_members_literal(tmp_path: Path) -> None:
    """Literal paths without glob chars are passed through."""
    (tmp_path / "mypackage").mkdir()
    result = _expand_workspace_members(tmp_path, ["mypackage"])
    assert result == ["mypackage"]


def test_expand_members_mixed(tmp_path: Path) -> None:
    """Mix of glob + literal entries all expand correctly."""
    (tmp_path / "packages" / "pkg-a").mkdir(parents=True)
    (tmp_path / "standalone").mkdir()
    result = _expand_workspace_members(tmp_path, ["packages/*", "standalone"])
    assert sorted(result) == ["packages/pkg-a", "standalone"]


def test_expand_members_no_match(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Glob with no matching dirs returns empty list and logs warning."""
    with caplog.at_level(logging.WARNING):
        result = _expand_workspace_members(tmp_path, ["nonexistent/*"])
    assert result == []
    assert any("nonexistent" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_analyze_workspace_glob_members(tmp_path: Path) -> None:
    """analyze_workspace expands glob members and discovers packages."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    pkg_src = tmp_path / "packages" / "pkg-a" / "src" / "pkg_a"
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    (tmp_path / "packages" / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\ndependencies = []\n'
    )

    ws = analyze_workspace(tmp_path)
    assert len(ws.packages) > 0
    pkg_names = [p.name for p in ws.packages]
    assert "pkg_a" in pkg_names


def test_build_package_edges_glob(tmp_path: Path) -> None:
    """_build_package_edges finds edges with expanded glob paths."""
    pkg_a = tmp_path / "packages" / "pkg-a"
    pkg_b = tmp_path / "packages" / "pkg-b"
    pkg_a.mkdir(parents=True)
    pkg_b.mkdir(parents=True)
    (pkg_a / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\ndependencies = []\n'
    )
    (pkg_b / "pyproject.toml").write_text(
        '[project]\nname = "pkg-b"\nversion = "0.1.0"\ndependencies = ["pkg-a"]\n'
    )

    members = ["packages/pkg-a", "packages/pkg-b"]
    member_names = set(members)
    edges = _build_package_edges(tmp_path, members, member_names)
    assert len(edges) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_expand_members_nested_globs(tmp_path: Path) -> None:
    """Nested glob patterns like 'packages/*/subpkg' expand correctly."""
    (tmp_path / "packages" / "group" / "subpkg").mkdir(parents=True)
    result = _expand_workspace_members(tmp_path, ["packages/*/subpkg"])
    assert result == ["packages/group/subpkg"]


def test_expand_members_no_glob_chars(tmp_path: Path) -> None:
    """Entry without glob chars is treated as literal path."""
    (tmp_path / "standalone-pkg").mkdir()
    result = _expand_workspace_members(tmp_path, ["standalone-pkg"])
    assert result == ["standalone-pkg"]


def test_expand_members_glob_matches_files_not_dirs(tmp_path: Path) -> None:
    """Files matching glob are filtered out; only directories kept."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "README.md").write_text("hello")
    (tmp_path / "packages" / "pkg-a").mkdir()
    result = _expand_workspace_members(tmp_path, ["packages/*"])
    assert result == ["packages/pkg-a"]
