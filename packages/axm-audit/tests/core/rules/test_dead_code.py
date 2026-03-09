"""Tests for DeadCodeRule (axm-ast dead-code integration)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from axm_audit.core.rules.dead_code import DeadCodeRule


class TestDeadCodeRule:
    """Tests for DeadCodeRule (axm-ast dead-code integration)."""

    @pytest.fixture
    def rule(self) -> DeadCodeRule:
        """Return a DeadCodeRule instance."""
        from axm_audit.core.rules.dead_code import DeadCodeRule

        return DeadCodeRule()

    def test_dead_code_rule_id_format(self, rule: DeadCodeRule) -> None:
        """Rule ID should be QUALITY_DEAD_CODE."""
        assert rule.rule_id == "QUALITY_DEAD_CODE"

    def test_dead_code_success(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 90/100 and passed=False for 2 dead symbols."""
        from axm_audit.models.results import Severity

        # axm-ast is found on PATH
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        # Mock the direct subprocess.run call for analysis
        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(
            [
                {"name": "foo", "module_path": "a.py", "line": 10, "kind": "function"},
                {"name": "bar", "module_path": "b.py", "line": 20, "kind": "class"},
            ]
        )
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 90.0  # 100 - (2 * 5)
        assert result.severity == Severity.WARNING
        assert result.details["dead_count"] == 2
        assert len(result.details["symbols"]) == 2
        assert len(result.details["top_offenders"]) == 2

    def test_dead_code_perfect(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 100/100 and passed=True for 0 dead symbols."""
        from axm_audit.models.results import Severity

        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.passed
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert result.details["dead_count"] == 0
        assert result.details["symbols"] == []

    def test_dead_code_skipped_not_available(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should skip gracefully if axm-ast is not on PATH."""
        from axm_audit.models.results import Severity

        # shutil.which returns None → axm-ast not found
        mocker.patch("shutil.which", return_value=None)

        result = rule.check(tmp_path)

        assert result.passed  # Graceful skip shouldn't fail the build
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert "skipped" in result.details
        assert result.details["skipped"] is True
        assert "axm-ast is not available" in result.message

    def test_dead_code_json_decode_error(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should handle JSON parsing errors gracefully."""
        from axm_audit.models.results import Severity

        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "Not a JSON output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 0.0
        assert result.severity == Severity.ERROR
        assert "parse" in result.message.lower()

    def test_dead_code_subprocess_args(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should call axm-ast directly with project_path as argument."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        rule.check(tmp_path)

        mock_run.assert_called_once_with(
            ["axm-ast", "dead-code", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
