"""Tests for TestCoverageRule (pytest-cov integration)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from axm_audit.core.test_runner import TestReport
from axm_audit.models.results import CheckResult


class TestTestCoverageRule:
    """Tests for TestCoverageRule."""

    def _run_with_coverage(
        self,
        tmp_path: Path,
        report: TestReport | None = None,
    ) -> CheckResult:
        """Run TestCoverageRule with a mocked run_tests return.

        When *report* is provided, the mock ``run_tests`` returns it
        directly. If None, returns a default all-pass report.
        """
        from axm_audit.core.rules.coverage import TestCoverageRule

        if report is None:
            report = TestReport(passed=42, failed=0, duration=5.0, coverage=95.0)

        rule = TestCoverageRule()
        with patch("axm_audit.core.test_runner.run_tests", return_value=report):
            return rule.check(tmp_path)

    def test_good_coverage_passes(self, tmp_path: Path) -> None:
        """90% coverage → score=90, passed=True."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=42,
                failed=0,
                duration=5.0,
                coverage=90.0,
            ),
        )
        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 90

    def test_low_coverage_fails(self, tmp_path: Path) -> None:
        """50% coverage → score=50, passed=False."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=42,
                failed=0,
                duration=5.0,
                coverage=50.0,
            ),
        )
        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 50

    def test_no_coverage_file(self, tmp_path: Path) -> None:
        """No coverage data → score=0, passed=False."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=42,
                failed=0,
                duration=5.0,
                coverage=None,
            ),
        )
        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 0

    def test_rule_id(self) -> None:
        """Rule ID should be QUALITY_COVERAGE."""
        from axm_audit.core.rules.coverage import TestCoverageRule

        assert TestCoverageRule().rule_id == "QUALITY_COVERAGE"

    def test_failures_cause_fail(self, tmp_path: Path) -> None:
        """Tests with failures should cause passed=False even with good coverage."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=40,
                failed=2,
                duration=5.0,
                coverage=95.0,
            ),
        )
        assert result.passed is False
        assert result.details is not None
        assert "2 test(s) failed" in result.message

    def test_errors_cause_fail(self, tmp_path: Path) -> None:
        """Tests with errors should cause passed=False."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=40,
                failed=0,
                errors=1,
                duration=5.0,
                coverage=95.0,
            ),
        )
        assert result.passed is False
