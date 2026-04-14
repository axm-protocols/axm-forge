from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.rules.quality import DiffSizeRule


@pytest.fixture
def rule() -> DiffSizeRule:
    return DiffSizeRule()


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


def _mock_subprocess(mocker: MockerFixture, stdout: str) -> None:
    mock_result = MagicMock()
    mock_result.stdout = stdout
    mocker.patch(
        "axm_audit.core.rules.quality.subprocess.run",
        return_value=mock_result,
    )


def _mock_config(
    mocker: MockerFixture, ideal: int = 200, max_lines: int = 1000
) -> None:
    mocker.patch(
        "axm_audit.core.rules.quality._read_diff_config",
        return_value=(ideal, max_lines),
    )


class TestDiffSizeText:
    """Tests for DiffSizeRule._measure_diff text rendering."""

    def test_diff_size_passed_text_is_none(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        _mock_subprocess(mocker, " 1 file changed, 50 insertions(+)\n")
        _mock_config(mocker)
        mocker.patch.object(rule, "_parse_stat", return_value=50)
        mocker.patch.object(rule, "_compute_score", return_value=100)

        result = rule._measure_diff(project_path)

        assert result.passed is True
        assert result.text is None

    def test_diff_size_failed_text_contains_delta(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        _mock_subprocess(mocker, " 10 files changed, 1100 insertions(+)\n")
        _mock_config(mocker, ideal=200)
        mocker.patch.object(rule, "_parse_stat", return_value=1100)
        mocker.patch.object(rule, "_compute_score", return_value=0)

        result = rule._measure_diff(project_path)

        assert result.passed is False
        assert result.text is not None
        assert "lines \u0394" in result.text
        assert "     \u2022" in result.text

    def test_diff_size_no_changes_text_is_none(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        _mock_subprocess(mocker, "")

        result = rule._measure_diff(project_path)

        assert result.passed is True
        assert result.text is None


class TestDiffSizeTextEdgeCases:
    """Edge cases for score-threshold boundary."""

    def test_score_at_threshold_text_is_none(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        _mock_subprocess(mocker, " 5 files changed, 300 insertions(+)\n")
        _mock_config(mocker)
        mocker.patch.object(rule, "_parse_stat", return_value=300)
        mocker.patch.object(rule, "_compute_score", return_value=90)

        result = rule._measure_diff(project_path)

        assert result.passed is True
        assert result.text is None

    def test_score_below_threshold_text_has_delta(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        _mock_subprocess(mocker, " 5 files changed, 350 insertions(+)\n")
        _mock_config(mocker, ideal=200)
        mocker.patch.object(rule, "_parse_stat", return_value=350)
        mocker.patch.object(rule, "_compute_score", return_value=89)

        result = rule._measure_diff(project_path)

        assert result.passed is False
        assert result.text is not None
        assert "lines \u0394" in result.text
        assert "     \u2022" in result.text
