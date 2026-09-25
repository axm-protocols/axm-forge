"""Integration coverage for the provider-routed learning-profile check."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks import learning
from tests_axm_init._learning_provider import FakeLearningProvider

pytestmark = pytest.mark.integration


def test_learning_check_returns_the_provider_verdict(
    tmp_path: Path, fake_learning_provider: FakeLearningProvider
) -> None:
    """AC1: the check result is the installed provider's, for the same root."""
    tmp_path.joinpath("pyproject.toml").write_text(
        '[project]\nname = "vision-project"\n\n'
        '[tool.axm-init.learning]\ndomain = "vision"\nschema_version = 1\n'
    )

    result = learning.check_learning_profile(tmp_path)

    assert result.passed is True
    assert result.category == "learning"
    assert "vision" in result.message
    assert fake_learning_provider.calls == [("check_learning_profile", (tmp_path,))]


def test_learning_check_reports_a_failing_provider_verdict(
    tmp_path: Path, fake_learning_provider: FakeLearningProvider
) -> None:
    """AC2: a provider failure is surfaced as-is, never softened by Forge."""
    tmp_path.joinpath("pyproject.toml").write_text('[project]\nname = "plain"\n')

    result = learning.check_learning_profile(tmp_path)

    assert result.passed is False
    assert result.fix
