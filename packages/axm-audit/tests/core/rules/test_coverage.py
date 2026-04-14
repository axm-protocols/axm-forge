"""Tests for TestCoverageRule (pytest-cov integration)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from axm_audit.core.rules.coverage import TestCoverageRule
from axm_audit.core.test_runner import FailureDetail, TestReport
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


def _make_failure(test: str = "tests/test_x.py::TestX::test_y") -> FailureDetail:
    return FailureDetail(
        test=test,
        error_type="AssertionError",
        message="boom",
        file="tests/test_x.py",
        line=1,
        traceback="",
    )


class TestReportToResultText:
    """Tests for _report_to_result text rendering (compact format)."""

    def _result(self, report: TestReport) -> CheckResult:
        return TestCoverageRule()._report_to_result(report)

    def test_text_coverage_line_compact(self) -> None:
        result = self._result(TestReport(coverage=82.0, failed=0))
        assert result.text == "\u2022 cov 82% \u2192 100%"

    def test_text_fail_short_name(self) -> None:
        report = TestReport(
            coverage=75.0,
            failed=1,
            failures=[_make_failure("tests/test_foo.py::TestFoo::test_bar")],
        )
        result = self._result(report)
        assert result.text is not None
        assert "\u2022 FAIL test_bar" in result.text

    def test_text_no_padding(self) -> None:
        report = TestReport(
            coverage=50.0,
            failed=1,
            failures=[_make_failure()],
        )
        result = self._result(report)
        assert result.text is not None
        for line in result.text.splitlines():
            assert not line.startswith(" ")

    def test_text_none_full_coverage(self) -> None:
        result = self._result(TestReport(coverage=100.0, failed=0))
        assert result.text is None

    def test_text_fail_no_separator(self) -> None:
        """Failure test id without '::' is returned unchanged."""
        report = TestReport(
            coverage=80.0,
            failed=1,
            failures=[_make_failure("test_simple")],
        )
        result = self._result(report)
        assert result.text is not None
        assert "\u2022 FAIL test_simple" in result.text

    def test_text_ten_plus_failures(self) -> None:
        """Only the first 10 failures are rendered."""
        failures = [_make_failure(f"t::test_{i}") for i in range(12)]
        report = TestReport(coverage=60.0, failed=12, failures=failures)
        result = self._result(report)
        assert result.text is not None
        fail_lines = [line for line in result.text.splitlines() if "FAIL" in line]
        assert len(fail_lines) == 10

    def test_text_full_coverage_with_failure(self) -> None:
        """100% coverage + 1 failure -> no coverage line, only FAIL line."""
        report = TestReport(
            coverage=100.0,
            failed=1,
            failures=[_make_failure("t::test_x")],
        )
        result = self._result(report)
        assert result.text is not None
        assert "cov" not in result.text
        assert "\u2022 FAIL test_x" in result.text
