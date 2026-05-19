"""Split from ``test_workspace.py``."""

from pathlib import Path

import pytest

from axm_ast.core.workspace import detect_workspace


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
    """Non-workspace setups return None.

    Covers: regular project, missing pyproject, empty members.
    """
    if pyproject_content is not None:
        (tmp_path / "pyproject.toml").write_text(
            pyproject_content,
            encoding="utf-8",
        )
    assert detect_workspace(tmp_path) is None
