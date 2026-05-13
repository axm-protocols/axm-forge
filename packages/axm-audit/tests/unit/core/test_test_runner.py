"""Unit tests for axm_audit.core.test_runner (pure parsing, no I/O)."""

from __future__ import annotations

from typing import Any

import pytest

from axm_audit.core.test_runner import (
    FailureDetail,
    parse_collector_errors,
    parse_failures,
)

_PUBLIC = (
    "build_test_report",
    "parse_coverage",
    "parse_failures",
    "parse_json_report",
    "parse_collector_errors",
    "build_pytest_cmd",
)

_SETUP_ERROR_REPORT: dict[str, Any] = {
    "summary": {"passed": 0, "failed": 0, "error": 1},
    "tests": [
        {
            "nodeid": "tests/test_models.py::test_budget",
            "outcome": "error",
            "setup": {
                "crash": {
                    "path": "tests/test_models.py",
                    "lineno": 12,
                    "message": "ValidationError: 7 validation errors for BudgetData",
                },
                "longrepr": (
                    "line1\nline2\nline3\n"
                    "ValidationError: 7 validation errors for BudgetData"
                ),
            },
            # No "call" key — collection error
        },
    ],
}

_FAILING_REPORT: dict[str, Any] = {
    "summary": {
        "passed": 40,
        "failed": 2,
        "error": 0,
        "skipped": 0,
        "warnings": 0,
        "duration": 8.3,
    },
    "tests": [
        {"nodeid": "tests/test_foo.py::test_ok", "outcome": "passed"},
        {
            "nodeid": "tests/test_foo.py::TestClass::test_fail",
            "outcome": "failed",
            "call": {
                "crash": {
                    "path": "tests/test_foo.py",
                    "lineno": 54,
                    "message": "AssertionError: 0 != 1",
                },
                "longrepr": "line1\nline2\nline3\nline4\nline5\nline6\nline7",
            },
        },
        {
            "nodeid": "tests/test_bar.py::test_error",
            "outcome": "error",
            "call": {
                "crash": {
                    "path": "tests/test_bar.py",
                    "lineno": 10,
                    "message": "ImportError: no module named 'foo'",
                },
                "longrepr": "short tb",
            },
        },
    ],
}

_COLLECTOR_ERROR_ENTRIES: list[dict[str, Any]] = [
    {
        "nodeid": "tests/test_broken.py",
        "outcome": "failed",
        "longrepr": (
            "tests/test_broken.py:1: in <module>\n"
            "    import nonexistent\n"
            "ModuleNotFoundError: No module named 'nonexistent'"
        ),
    },
]


class TestParseFailures:
    def test_empty_list(self) -> None:
        assert parse_failures([]) == []

    def test_passing_tests_skipped(self) -> None:
        tests = [{"nodeid": "test_a", "outcome": "passed"}]
        assert parse_failures(tests) == []

    def test_failed_test_extracted(self) -> None:
        result = parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        f = result[0]
        assert isinstance(f, FailureDetail)
        assert f.test == "tests/test_foo.py::TestClass::test_fail"
        assert f.error_type == "AssertionError"
        assert f.file == "tests/test_foo.py"
        assert f.line == 54

    def test_traceback_truncated(self) -> None:
        """Traceback longer than 5 lines is truncated."""
        result = parse_failures(_FAILING_REPORT["tests"])
        tb_lines = result[0].traceback.splitlines()
        assert len(tb_lines) <= 5

    def test_error_outcome_included(self) -> None:
        result = parse_failures(_FAILING_REPORT["tests"])
        err = result[1]
        assert err.error_type == "ImportError"
        assert err.test == "tests/test_bar.py::test_error"

    def test_parse_failures_collection_error(self) -> None:
        """Setup-phase errors (no 'call' key) produce non-empty FailureDetail."""
        result = parse_failures(_SETUP_ERROR_REPORT["tests"])
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_models.py::test_budget"
        assert f.error_type == "ValidationError"
        assert f.traceback != ""
        assert f.message != ""
        assert f.file == "tests/test_models.py"
        assert f.line == 12

    def test_parse_failures_call_error_unchanged(self) -> None:
        """Normal call-phase failures are unaffected by the fallback logic."""
        result = parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        assert result[0].error_type == "AssertionError"
        assert result[0].file == "tests/test_foo.py"
        assert result[0].line == 54
        assert result[1].error_type == "ImportError"


class TestParseCollectorErrors:
    def test_empty_list(self) -> None:
        assert parse_collector_errors([]) == []

    def test_collector_without_longrepr_skipped(self) -> None:
        result = parse_collector_errors([{"nodeid": "foo", "longrepr": ""}])
        assert result == []

    def test_parse_failures_collector_error(self) -> None:
        """Collector-level errors produce FailureDetail with correct fields."""
        result = parse_collector_errors(_COLLECTOR_ERROR_ENTRIES)
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_broken.py"
        assert f.error_type == "ModuleNotFoundError"
        assert "nonexistent" in f.message
        assert f.traceback != ""


def test_test_runner_public_parsing_api() -> None:
    """All parsing helpers importable as public symbols."""
    from axm_audit.core import test_runner

    for name in _PUBLIC:
        assert hasattr(test_runner, name), f"missing public symbol: {name}"
        assert callable(getattr(test_runner, name))


@pytest.mark.parametrize("name", _PUBLIC)
def test_private_alias_removed(name: str) -> None:
    """Underscore-prefixed aliases removed (no shim left behind)."""
    from axm_audit.core import test_runner

    assert not hasattr(test_runner, f"_{name}"), (
        f"deprecated private alias _{name} still exposed"
    )


# --- build_test_report: unified report parsing ---


from axm_audit.core.test_runner import TestReport, build_test_report  # noqa: E402


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
        assert report.coverage_by_file == per_file
        assert report.failures is not None
        assert len(report.failures) == 1
