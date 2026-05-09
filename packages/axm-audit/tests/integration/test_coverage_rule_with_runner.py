"""Integration tests: TestCoverageRule x test_runner (mocked runner)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.core.rules.coverage import TestCoverageRule
from axm_audit.core.test_runner import TestReport
from axm_audit.models.results import CheckResult

pytestmark = pytest.mark.integration


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

        if report is None:
            report = TestReport(passed=42, failed=0, duration=5.0, coverage=95.0)

        rule = TestCoverageRule()
        with patch("axm_audit.core.test_runner.run_tests", return_value=report):
            return rule.check(tmp_path)

    @pytest.mark.parametrize(
        ("report", "expected_passed", "expected_score"),
        [
            pytest.param(
                TestReport(passed=42, failed=0, duration=5.0, coverage=90.0),
                True,
                90,
                id="good_coverage",
            ),
            pytest.param(
                TestReport(passed=42, failed=0, duration=5.0, coverage=50.0),
                False,
                None,
                id="low_coverage",
            ),
            pytest.param(
                TestReport(passed=42, failed=0, duration=5.0, coverage=None),
                False,
                0,
                id="no_coverage_data",
            ),
            pytest.param(
                TestReport(passed=40, failed=0, errors=1, duration=5.0, coverage=95.0),
                False,
                None,
                id="errors_present",
            ),
        ],
    )
    def test_classifies_report(
        self,
        tmp_path: Path,
        report: TestReport,
        expected_passed: bool,
        expected_score: int | None,
    ) -> None:
        """Rule maps (coverage, failures, errors) to (passed, score) correctly."""
        result = self._run_with_coverage(tmp_path, report=report)
        assert result.passed is expected_passed
        assert result.details is not None
        if expected_score is not None:
            assert result.score == expected_score

    def test_fix_hints_both(self, tmp_path: Path) -> None:
        """Tests that fix hints include both failures and coverage increase."""
        result = self._run_with_coverage(
            tmp_path,
            report=TestReport(
                passed=40,
                failed=1,
                errors=0,
                duration=5.0,
                coverage=50.0,
            ),
        )
        assert result.passed is False
        assert result.fix_hint is not None
        assert "Fix failing tests" in result.fix_hint
        assert "Increase test coverage" in result.fix_hint
        assert result.details is not None
        assert result.score == 50

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
