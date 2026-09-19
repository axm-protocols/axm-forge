"""Integration coverage for declared learning-profile conformance."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _write_project(project: Path, *, study: bool = True, training: bool = True) -> None:
    project.joinpath("pyproject.toml").write_text(
        '[project]\nname = "vision-project"\n\n'
        '[tool.axm-init.learning]\ndomain = "vision"\nschema_version = 1\n'
    )
    if study:
        project.joinpath("study.toml").write_text('[study]\nname = "vision"\n')
    if training:
        project.joinpath("training.toml").write_text('[training]\nname = "vision"\n')


def test_declared_learning_profile_with_generated_files_passes(tmp_path: Path) -> None:
    """AC1: a complete declared profile passes and names its domain."""
    from axm_init.checks import learning

    _write_project(tmp_path)

    result = learning.check_learning_profile(tmp_path)

    assert result.passed is True
    assert result.category == "learning"
    assert "vision" in result.message


def test_declared_learning_profile_missing_study_fails(tmp_path: Path) -> None:
    """AC2: a missing study file is named with an actionable correction."""
    from axm_init.checks import learning

    _write_project(tmp_path, study=False)

    result = learning.check_learning_profile(tmp_path)

    assert result.passed is False
    assert any("study.toml" in detail for detail in result.details)
    assert result.fix


def test_undeclared_learning_profile_passes_at_zero_weight(tmp_path: Path) -> None:
    """AC3: a project without a learning declaration is neutral in scoring."""
    from axm_init.checks import learning

    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "ordinary-project"\n\n[tool.axm-init]\n'
    )

    result = learning.check_learning_profile(tmp_path)

    assert result.passed is True
    assert result.weight == 0
