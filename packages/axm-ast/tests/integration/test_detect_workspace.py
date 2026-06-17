"""Split from ``test_workspace.py``."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from axm_ast.core.workspace import detect_workspace
from axm_ast.models.nodes import WorkspaceInfo


def _write_workspace(root: Path) -> None:
    """Write a minimal uv-workspace pyproject.toml at ``root``."""
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "my-workspace"\n'
        'version = "0.1.0"\n'
        "\n"
        "[tool.uv.workspace]\n"
        'members = ["packages/*"]\n',
        encoding="utf-8",
    )
    pkg = root / "packages" / "pkg-a"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def test_returns_workspace_info(tmp_path: Path) -> None:
    """AC1: detect_workspace returns a WorkspaceInfo with correct root and name."""
    _write_workspace(tmp_path)

    ws = detect_workspace(tmp_path)

    assert ws is not None
    assert isinstance(ws, WorkspaceInfo)
    assert ws.root == tmp_path.resolve()
    assert ws.name == "my-workspace"


@pytest.mark.parametrize(
    ("pyproject_content",),
    [
        pytest.param(
            '[project]\nname = "regular"\nversion = "0.1.0"\n',
            id="regular_project",
        ),
        pytest.param(None, id="no_pyproject"),
        pytest.param(
            '[project]\nname = "x"\n\n[tool.uv.workspace]\nmembers = []\n',
            id="empty_members",
        ),
    ],
)
def test_detect_workspace_returns_none(
    tmp_path: Path, pyproject_content: str | None
) -> None:
    """AC1: non-workspace setups return None.

    Covers: regular project, missing pyproject, empty members.
    """
    if pyproject_content is not None:
        (tmp_path / "pyproject.toml").write_text(
            pyproject_content,
            encoding="utf-8",
        )
    assert detect_workspace(tmp_path) is None


def test_none_when_not_workspace(tmp_path: Path) -> None:
    """AC1: detect_workspace returns None for a plain (non-workspace) pyproject."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    assert detect_workspace(tmp_path) is None


def test_workspace_info_is_pydantic() -> None:
    """AC2: WorkspaceInfo stays a Pydantic BaseModel defined in axm-ast."""
    assert issubclass(WorkspaceInfo, BaseModel)
    assert WorkspaceInfo.__module__ == "axm_ast.models.nodes"

    ws = WorkspaceInfo(name="x", root=Path("/ws"))
    assert ws.name == "x"
    assert ws.packages == []
