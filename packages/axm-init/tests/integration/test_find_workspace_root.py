"""Split from ``test_workspace_context_detection.py``."""

from pathlib import Path

import pytest

from axm_init.checks._workspace import find_workspace_root
from tests.integration._helpers import STANDALONE_TOML


@pytest.fixture()
def standalone_project(tmp_path: Path) -> Path:
    """A standalone package (no workspace)."""
    (tmp_path / "pyproject.toml").write_text(STANDALONE_TOML)
    return tmp_path


@pytest.fixture()
def member_path(workspace_root__from_workspace_context_detection: Path) -> Path:
    """Path to a member package inside the workspace."""
    return workspace_root__from_workspace_context_detection / "packages" / "pkg-a"


class TestFindWorkspaceRoot:
    def test_from_member(
        self, workspace_root__from_workspace_context_detection: Path, member_path: Path
    ) -> None:
        root = find_workspace_root(member_path)
        assert root is not None
        assert (
            root.resolve() == workspace_root__from_workspace_context_detection.resolve()
        )

    def test_standalone_returns_none(self, standalone_project: Path) -> None:
        assert find_workspace_root(standalone_project) is None
