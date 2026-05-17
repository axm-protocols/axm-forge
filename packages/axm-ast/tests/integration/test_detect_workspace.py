"""Split from ``test_workspace.py``."""

from pathlib import Path

from axm_ast.core.workspace import detect_workspace


def test_detect_workspace_none_regular_project(tmp_path: Path) -> None:
    """Regular project without workspace section returns None."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "regular"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    assert detect_workspace(tmp_path) is None


def test_detect_workspace_no_pyproject(tmp_path: Path) -> None:
    """Directory without pyproject.toml returns None."""
    assert detect_workspace(tmp_path) is None


def test_detect_workspace_empty_members(tmp_path: Path) -> None:
    """Workspace with empty members list returns None."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[tool.uv.workspace]\nmembers = []\n',
        encoding="utf-8",
    )
    assert detect_workspace(tmp_path) is None
