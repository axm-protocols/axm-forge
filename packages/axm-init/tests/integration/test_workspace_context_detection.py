"""Tests for checks._workspace — workspace context detection."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
    find_workspace_root,
    get_workspace_members,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WORKSPACE_TOML = dedent("""\
    [project]
    name = "my-workspace"

    [tool.uv.workspace]
    members = ["packages/*"]
""")

WORKSPACE_TOML_WITH_EXCLUDE = dedent("""\
    [project]
    name = "my-workspace"

    [tool.uv.workspace]
    members = ["packages/*"]
    exclude = ["packages/internal"]
""")

STANDALONE_TOML = dedent("""\
    [project]
    name = "standalone-pkg"

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"
""")

MEMBER_TOML = dedent("""\
    [project]
    name = "member-pkg"
""")


@pytest.fixture()
def standalone_project(tmp_path: Path) -> Path:
    """A standalone package (no workspace)."""
    (tmp_path / "pyproject.toml").write_text(STANDALONE_TOML)
    return tmp_path


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """A UV workspace root with two member packages."""
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_TOML)
    for pkg_name in ("pkg-a", "pkg-b"):
        pkg = tmp_path / "packages" / pkg_name
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\n')
    return tmp_path


@pytest.fixture()
def member_path(workspace_root: Path) -> Path:
    """Path to a member package inside the workspace."""
    return workspace_root / "packages" / "pkg-a"


# ---------------------------------------------------------------------------
# TestDetectContext
# ---------------------------------------------------------------------------


class TestDetectContext:
    def test_detect_standalone(self, standalone_project: Path) -> None:
        assert detect_context(standalone_project) == ProjectContext.STANDALONE

    def test_detect_workspace(self, workspace_root: Path) -> None:
        assert detect_context(workspace_root) == ProjectContext.WORKSPACE

    def test_detect_member(self, member_path: Path) -> None:
        assert detect_context(member_path) == ProjectContext.MEMBER


# ---------------------------------------------------------------------------
# TestFindWorkspaceRoot
# ---------------------------------------------------------------------------


class TestFindWorkspaceRoot:
    def test_from_member(self, workspace_root: Path, member_path: Path) -> None:
        root = find_workspace_root(member_path)
        assert root is not None
        assert root.resolve() == workspace_root.resolve()

    def test_standalone_returns_none(self, standalone_project: Path) -> None:
        assert find_workspace_root(standalone_project) is None


# ---------------------------------------------------------------------------
# TestGetWorkspaceMembers
# ---------------------------------------------------------------------------


class TestGetWorkspaceMembers:
    def test_basic(self, workspace_root: Path) -> None:
        members = get_workspace_members(workspace_root)
        assert members == ["pkg-a", "pkg-b"]

    def test_with_exclude(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(WORKSPACE_TOML_WITH_EXCLUDE)
        for pkg_name in ("pkg-a", "internal"):
            pkg = tmp_path / "packages" / pkg_name
            pkg.mkdir(parents=True)
            (pkg / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\n')
        members = get_workspace_members(tmp_path)
        assert "internal" not in members
        assert "pkg-a" in members

    def test_empty(self, tmp_path: Path) -> None:
        """Workspace with no matching member directories."""
        toml = dedent("""\
            [project]
            name = "empty-ws"

            [tool.uv.workspace]
            members = ["nonexistent/*"]
        """)
        (tmp_path / "pyproject.toml").write_text(toml)
        assert get_workspace_members(tmp_path) == []


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_pyproject(self, tmp_path: Path) -> None:
        """Directory with no pyproject.toml → STANDALONE."""
        assert detect_context(tmp_path) == ProjectContext.STANDALONE

    def test_corrupt_toml(self, tmp_path: Path) -> None:
        """Invalid pyproject.toml → STANDALONE (graceful fallback)."""
        (tmp_path / "pyproject.toml").write_text("{{invalid toml!!")
        assert detect_context(tmp_path) == ProjectContext.STANDALONE

    def test_nested_workspaces(self, tmp_path: Path) -> None:
        """Workspace inside another workspace → detects nearest parent."""
        # Outer workspace
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "outer"

            [tool.uv.workspace]
            members = ["inner"]
        """)
        )
        # Inner workspace (also a workspace root itself)
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "inner"

            [tool.uv.workspace]
            members = ["packages/*"]
        """)
        )
        # Inner is itself a WORKSPACE (it has [tool.uv.workspace])
        assert detect_context(inner) == ProjectContext.WORKSPACE

        # A package inside inner should find inner as root, not outer
        pkg = inner / "packages" / "deep"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text('[project]\nname = "deep"\n')
        root = find_workspace_root(pkg)
        assert root is not None
        assert root.resolve() == inner.resolve()

    def test_glob_no_match(self, tmp_path: Path) -> None:
        """members glob matches no dirs → empty list."""
        (tmp_path / "pyproject.toml").write_text(
            dedent("""\
            [project]
            name = "ws"

            [tool.uv.workspace]
            members = ["nonexistent/*"]
        """)
        )
        assert get_workspace_members(tmp_path) == []

    def test_get_members_no_pyproject(self, tmp_path: Path) -> None:
        """get_workspace_members on path without pyproject.toml → empty."""
        assert get_workspace_members(tmp_path) == []


# ---------------------------------------------------------------------------
