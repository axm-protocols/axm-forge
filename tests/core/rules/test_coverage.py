"""Tests for TestCoverageRule (pytest-cov integration)."""

import json
from pathlib import Path
from unittest.mock import patch


class TestTestCoverageRule:
    """Tests for TestCoverageRule."""

    def test_good_coverage_passes(self, tmp_path: Path) -> None:
        """90% coverage → score=90, passed=True."""
        from axm_audit.core.rules.quality import TestCoverageRule

        coverage_data = {"totals": {"percent_covered": 90.0}}
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        mock_result = type(
            "Result", (), {"stdout": "", "stderr": "", "returncode": 0}
        )()

        rule = TestCoverageRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 90

    def test_low_coverage_fails(self, tmp_path: Path) -> None:
        """50% coverage → score=50, passed=False."""
        from axm_audit.core.rules.quality import TestCoverageRule

        coverage_data = {"totals": {"percent_covered": 50.0}}
        coverage_file = tmp_path / "coverage.json"
        coverage_file.write_text(json.dumps(coverage_data))

        mock_result = type(
            "Result", (), {"stdout": "", "stderr": "", "returncode": 0}
        )()

        rule = TestCoverageRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 50

    def test_no_coverage_file(self, tmp_path: Path) -> None:
        """No coverage.json → score=0, passed=False."""
        from axm_audit.core.rules.quality import TestCoverageRule

        mock_result = type(
            "Result", (), {"stdout": "", "stderr": "", "returncode": 1}
        )()

        rule = TestCoverageRule()
        with patch("subprocess.run", return_value=mock_result):
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 0

    def test_rule_id(self) -> None:
        """Rule ID should be QUALITY_COVERAGE."""
        from axm_audit.core.rules.quality import TestCoverageRule

        assert TestCoverageRule().rule_id == "QUALITY_COVERAGE"
