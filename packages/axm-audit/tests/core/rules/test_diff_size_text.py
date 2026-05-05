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
        "axm_audit.core.rules.quality.read_diff_config",
        return_value=(ideal, max_lines),
    )


class TestDiffSizeText:
    """Tests for DiffSizeRule._measure_diff text rendering."""

    @pytest.mark.parametrize(
        ("stdout", "lines", "score", "expected_passed"),
        [
            pytest.param(
                " 1 file changed, 50 insertions(+)\n",
                50,
                100,
                True,
                id="passed_low_lines",
            ),
            pytest.param(
                " 5 files changed, 300 insertions(+)\n",
                300,
                90,
                True,
                id="passed_at_threshold",
            ),
            pytest.param(
                " 10 files changed, 1100 insertions(+)\n",
                1100,
                0,
                False,
                id="failed_high_lines",
            ),
            pytest.param(
                " 5 files changed, 350 insertions(+)\n",
                350,
                89,
                False,
                id="failed_below_threshold",
            ),
        ],
    )
    def test_measure_diff_text_rendering(  # noqa: PLR0913 — pytest fixtures + parametrize args
        self,
        rule: DiffSizeRule,
        project_path: Path,
        mocker: MockerFixture,
        stdout: str,
        lines: int,
        score: int,
        expected_passed: bool,
    ) -> None:
        """Text is None when passed; contains delta marker when failed."""
        _mock_subprocess(mocker, stdout)
        _mock_config(mocker, ideal=200)
        mocker.patch.object(rule, "_parse_stat", return_value=lines)
        mocker.patch.object(rule, "compute_score", return_value=score)

        result = rule._measure_diff(project_path)

        assert result.passed is expected_passed
        if expected_passed:
            assert result.text is None
        else:
            assert result.text is not None
            assert "lines \u0394" in result.text
            assert "\u2022" in result.text

    def test_diff_size_no_changes_text_is_none(
        self, rule: DiffSizeRule, project_path: Path, mocker: MockerFixture
    ) -> None:
        """Empty git diff stdout short-circuits to passed with no text."""
        _mock_subprocess(mocker, "")

        result = rule._measure_diff(project_path)

        assert result.passed is True
        assert result.text is None
