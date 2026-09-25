from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from axm_init.tools.scaffold import InitScaffoldTool
from tests_axm_init._learning_provider import FakeLearningProvider
from tests_axm_init.conftest import (
    materialize_post_copy_artifacts,
    scaffold_without_tasks,
)

pytestmark = pytest.mark.integration


def test_composed_learning_pyproject_keeps_profile_and_base_tooling(
    tmp_path: Path, fake_learning_provider: FakeLearningProvider
) -> None:
    """AC1: composed metadata contains learning and base-tooling contracts."""
    root = tmp_path / "learning-lab"
    with scaffold_without_tasks():
        result = InitScaffoldTool().execute(
            path=str(root),
            name="learning-lab",
            kind="learning",
            domain="forecasting",
            org="test-org",
            author="Test Author",
            email="test@example.com",
        )
    assert result.success is True, result.error
    materialize_post_copy_artifacts(root)

    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["tool"]["axm-init"]["learning"]["domain"] == "forecasting"
    assert isinstance(metadata["tool"]["mypy"], dict)
    assert isinstance(metadata["tool"]["coverage"]["run"], dict)
    assert isinstance(metadata["tool"]["hatch"]["version"], dict)
    assert isinstance(metadata["tool"]["git-cliff"]["git"], dict)
    assert isinstance(metadata["dependency-groups"], dict)
