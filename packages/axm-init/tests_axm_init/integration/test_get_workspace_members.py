"""Split from ``test_workspace_context_detection.py``."""

from pathlib import Path
from textwrap import dedent

import pytest

from axm_init.checks._workspace import get_workspace_members

WORKSPACE_TOML_WITH_EXCLUDE = dedent("""\
    [project]
    name = "my-workspace"

    [tool.uv.workspace]
    members = ["packages/*"]
    exclude = ["packages/internal"]
""")


class TestGetWorkspaceMembers:
    def test_basic(
        self, workspace_root__from_workspace_context_detection: Path
    ) -> None:
        members = get_workspace_members(
            workspace_root__from_workspace_context_detection
        )
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
