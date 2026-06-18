"""Tests for TestCoverageRule (pytest-cov integration)."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.coverage import TestCoverageRule, read_coverage_config
from axm_audit.core.test_runner import FailureDetail, TestReport
from axm_audit.models.results import CheckResult


def test_rule_id() -> None:
    """Rule ID should be QUALITY_COVERAGE."""
    assert TestCoverageRule().rule_id == "QUALITY_COVERAGE"


def _write_pyproject(tmp_path: Path, body: str) -> Path:
    """Write a pyproject.toml with ``body`` into ``tmp_path`` and return it."""
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")
    return tmp_path


def test_read_coverage_config_default_when_absent(tmp_path: Path) -> None:
    """AC1: a pyproject lacking the section returns the default 90.0."""
    project = _write_pyproject(
        tmp_path,
        '[project]\nname = "demo"\nversion = "0.1.0"\n',
    )

    assert read_coverage_config(project) == 90.0


def test_read_coverage_config_returns_configured(tmp_path: Path) -> None:
    """AC1: a configured ``min_coverage`` is read back as a float."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 75\n",
    )

    assert read_coverage_config(project) == 75.0


def test_read_coverage_config_zero(tmp_path: Path) -> None:
    """AC5: ``min_coverage = 0`` is a valid in-bounds value, returned as 0.0."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 0\n",
    )

    assert read_coverage_config(project) == 0.0


def test_read_coverage_config_out_of_bounds_falls_back(tmp_path: Path) -> None:
    """AC2: out-of-[0,100] or non-numeric values fall back to the default 90.0."""
    too_high = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 150\n",
    )
    assert read_coverage_config(too_high) == 90.0

    non_numeric = _write_pyproject(
        tmp_path,
        '[tool.axm-audit.coverage]\nmin_coverage = "high"\n',
    )
    assert read_coverage_config(non_numeric) == 90.0


def test_read_coverage_config_malformed_toml(tmp_path: Path) -> None:
    """AC1: invalid TOML never raises — falls back to the default 90.0."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage\nmin_coverage = = 75\n",
    )

    assert read_coverage_config(project) == 90.0


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

    def test_timeout_reports_explicit_failure(self) -> None:
        """AC2: a timed-out ``TestReport`` becomes a ``CheckResult`` whose
        message/fix_hint makes the timeout explicit — never a fabricated score.

        ``run_tests`` is imported locally inside ``check`` (``from
        axm_audit.core.test_runner import run_tests``), so it is patched at
        its definition site ``axm_audit.core.test_runner.run_tests``.
        """
        from pathlib import Path
        from unittest.mock import patch

        timed_out_report = TestReport(
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            warnings=0,
            duration=0.0,
            coverage=None,
            timed_out=True,
        )
        with patch(
            "axm_audit.core.test_runner.run_tests",
            return_value=timed_out_report,
        ):
            result = TestCoverageRule().check(Path("/nonexistent/project"))

        assert result.passed is False
        blob = f"{result.message} {getattr(result, 'fix_hint', '') or ''}".lower()
        assert "timed out" in blob or "timeout" in blob or "not measured" in blob

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
