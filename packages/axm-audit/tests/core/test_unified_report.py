from __future__ import annotations

from axm_audit.core.test_runner import (
    TestReport,
    build_test_report,
    run_tests,
)


def _make_report_data(*, num_failed: int = 0, num_passed: int = 5) -> dict[str, object]:
    """Build minimal pytest JSON report data."""
    tests: list[dict[str, object]] = []
    for i in range(num_passed):
        tests.append(
            {"nodeid": f"tests/test_ex.py::test_pass_{i}", "outcome": "passed"}
        )
    for i in range(num_failed):
        tests.append(
            {
                "nodeid": f"tests/test_ex.py::test_fail_{i}",
                "outcome": "failed",
                "call": {"longrepr": f"AssertionError: {i}"},
            }
        )
    return {
        "summary": {
            "passed": num_passed,
            "failed": num_failed,
            "error": 0,
            "skipped": 0,
            "warnings": 0,
        },
        "tests": tests,
        "duration": 1.0,
    }


class TestBuildReportAlwaysParsesFailures:
    """AC1: _build_test_report always parses failures — no mode branching."""

    def test_build_report_always_parses_failures(self):
        report_data = _make_report_data(num_failed=1)
        report = build_test_report(
            report_data=report_data,
            total_cov=80.0,
            per_file_cov={"src/a.py": 80.0},
        )
        assert report.failures is not None
        assert len(report.failures) == 1


class TestBuildReportCoverageNone:
    """AC4: coverage_by_file is None when no coverage data."""

    def test_build_report_coverage_none_when_empty(self):
        report_data = _make_report_data()
        report = build_test_report(
            report_data=report_data,
            total_cov=None,
            per_file_cov={},
        )
        assert report.coverage_by_file is None


class TestBuildReportFailuresNone:
    """AC5: failures is None when no failures exist."""

    def test_build_report_failures_none_when_no_fails(self):
        report_data = _make_report_data(num_failed=0)
        report = build_test_report(
            report_data=report_data,
            total_cov=90.0,
            per_file_cov={"src/a.py": 90.0},
        )
        assert report.failures is None


class TestRunTestsIgnoresMode:
    """AC3: run_tests still accepts mode but ignores it."""

    def test_run_tests_ignores_mode(self, monkeypatch, tmp_path):
        report_data = _make_report_data(num_failed=1, num_passed=3)
        per_file = {"src/a.py": 75.0}

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_json_report",
            lambda _: report_data,
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_coverage",
            lambda _: (75.0, per_file),
        )

        report = run_tests(tmp_path, mode="compact")

        # Coverage always collected even with compact mode
        assert report.coverage == 75.0
        assert report.coverage_by_file == per_file
        # Failures always parsed (was skipped for compact before)
        assert report.failures is not None
        assert len(report.failures) == 1


class TestCoverageRuleHandlesFailuresNone:
    """Edge: _report_to_result handles failures=None without crash."""

    def test_report_to_result_failures_none(self):
        from axm_audit.core.rules.coverage import TestCoverageRule

        rule = TestCoverageRule()
        report = TestReport(
            passed=5,
            failed=0,
            errors=0,
            coverage=80.0,
            failures=None,
        )
        result = rule._report_to_result(report)
        # Should not crash and should produce empty failures list
        details = result.details
        assert details is not None
        assert details["failures"] == []


class TestDeprecatedDeltaMode:
    """Edge: delta mode accepted silently, same behavior as any other mode."""

    def test_delta_mode_same_behavior(self):
        report_data = _make_report_data(num_failed=1)
        per_file = {"src/a.py": 85.0}
        report = build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file,
        )
        # Always gets per_file_cov directly — no delta computation
        assert report.coverage_by_file == per_file
        assert report.failures is not None
        assert len(report.failures) == 1
