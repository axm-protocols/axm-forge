"""Integration: workspace-category run on a standalone project is N/A."""

from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine
from axm_init.models.check import ProjectResult


@pytest.fixture()
def standalone_path(tmp_path: Path) -> Path:
    """A minimal standalone (non-workspace) project."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\n')
    return tmp_path


def test_workspace_category_on_standalone_is_not_applicable(
    standalone_path: Path,
) -> None:
    """Every workspace check skips on a standalone project → N/A, not a 0."""
    result: ProjectResult = CheckEngine(standalone_path, category="workspace").run()
    assert result.not_applicable is True
