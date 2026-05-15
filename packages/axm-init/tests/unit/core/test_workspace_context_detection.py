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
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param(
                "standalone_project", ProjectContext.STANDALONE, id="standalone"
            ),
            pytest.param("workspace_root", ProjectContext.WORKSPACE, id="workspace"),
            pytest.param("member_path", ProjectContext.MEMBER, id="member"),
        ],
    )
    def test_detect(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: ProjectContext,
    ) -> None:
        path = request.getfixturevalue(fixture_name)
        assert detect_context(path) == expected


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

    @pytest.mark.parametrize(
        "pyproject_content",
        [
            pytest.param(
                dedent("""\
                    [project]
                    name = "empty-ws"

                    [tool.uv.workspace]
                    members = ["nonexistent/*"]
                """),
                id="empty_glob",
            ),
            pytest.param(None, id="no_pyproject"),
        ],
    )
    def test_get_workspace_members_empty(
        self, tmp_path: Path, pyproject_content: str | None
    ) -> None:
        """get_workspace_members returns [] for empty workspaces or no pyproject."""
        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        assert get_workspace_members(tmp_path) == []


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(None, id="missing_pyproject"),
            pytest.param("{{invalid toml!!", id="corrupt_toml"),
        ],
    )
    def test_detect_context_falls_back_to_standalone(
        self, tmp_path: Path, content: str | None
    ) -> None:
        """Missing or corrupt pyproject.toml → STANDALONE (graceful fallback)."""
        if content is not None:
            (tmp_path / "pyproject.toml").write_text(content)
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


# ---------------------------------------------------------------------------
