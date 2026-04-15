from __future__ import annotations

from typing import Any
from unittest.mock import patch

from axm_audit.core.test_runner import FailureDetail, TestReport
from axm_audit.tools.audit_test_text import format_audit_test_text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _failure(nodeid: str = "tests/test_foo.py::test_bar", **kw: Any) -> FailureDetail:
    """Build a FailureDetail with sensible defaults."""
    # Map to actual FailureDetail field names
    if "nodeid" in kw:
        kw["test"] = kw.pop("nodeid")
    if "lineno" in kw:
        kw["line"] = kw.pop("lineno")
    defaults: dict[str, Any] = {
        "test": nodeid,
        "file": "src/foo.py",
        "line": 42,
        "error_type": "AssertionError",
        "message": "expected 5 got 3",
        "traceback": "assert 5 == 3\n  where 5 = func()",
    }
    defaults.update(kw)
    return FailureDetail(**defaults)


# ---------------------------------------------------------------------------
# Unit tests — green / red paths
# ---------------------------------------------------------------------------


def test_green_path_header_only():
    report = TestReport(passed=42, failed=0, coverage=95.0, duration=1.2)
    text = format_audit_test_text(report)
    assert text.startswith("audit_test | \u2705")
    assert "42 passed" in text
    assert "cov 95.0%" in text
    # Green path → single line
    assert "\n" not in text.strip() or all(
        not line.startswith("\u2717") for line in text.splitlines()
    )


def test_red_path_with_failures():
    failures = [
        _failure(nodeid="tests/test_a.py::test_one"),
        _failure(nodeid="tests/test_b.py::test_two", file="src/bar.py", lineno=99),
    ]
    report = TestReport(passed=10, failed=2, failures=failures, duration=3.5)
    text = format_audit_test_text(report)
    assert "\u274c" in text  # ❌ in header
    assert "10 passed" in text
    assert "2 failed" in text
    # Each failure block starts with ✗
    lines = text.splitlines()
    failure_lines = [line for line in lines if line.startswith("\u2717")]
    assert len(failure_lines) == 2


# ---------------------------------------------------------------------------
# Coverage tests
# ---------------------------------------------------------------------------


def test_coverage_filters_below_95():
    report = TestReport(
        passed=5,
        failed=0,
        coverage=90.0,
        coverage_by_file={"a.py": 100.0, "b.py": 80.0},
        duration=0.5,
    )
    text = format_audit_test_text(report)
    assert "b.py 80" in text
    assert "a.py" not in text.split("\n", 1)[-1] if "\n" in text else True


def test_coverage_omitted_when_none():
    report = TestReport(
        passed=5, failed=0, coverage=None, coverage_by_file=None, duration=0.5
    )
    text = format_audit_test_text(report)
    assert "cov" not in text.lower()


# ---------------------------------------------------------------------------
# Failures edge cases
# ---------------------------------------------------------------------------


def test_failures_none_no_crash():
    report = TestReport(passed=5, failed=0, failures=None, duration=0.5, coverage=80.0)
    text = format_audit_test_text(report)
    assert isinstance(text, str)
    # No failure section
    assert "\u2717" not in text


# ---------------------------------------------------------------------------
# Counts in header
# ---------------------------------------------------------------------------


def test_skipped_shown_when_nonzero():
    report = TestReport(passed=10, failed=0, skipped=3, duration=1.0, coverage=99.0)
    text = format_audit_test_text(report)
    assert "3 skipped" in text


def test_errors_shown_when_nonzero():
    report = TestReport(passed=10, failed=0, errors=2, duration=1.0, coverage=99.0)
    text = format_audit_test_text(report)
    assert "2 error" in text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_all_files_above_95_no_coverage_section():
    cov = {f"mod{i}.py": 95.0 + (i % 6) for i in range(50)}
    report = TestReport(
        passed=50, failed=0, coverage=98.0, coverage_by_file=cov, duration=2.0
    )
    text = format_audit_test_text(report)
    lines = text.splitlines()
    # Header has cov, but no per-file lines
    assert "cov" in lines[0]
    # No file-level coverage lines beyond header
    for line in lines[1:]:
        assert "%" not in line or line.strip().startswith("\u2717")


def test_very_long_test_name():
    long_name = "tests/test_x.py::test_" + "a" * 200
    failures = [_failure(nodeid=long_name)]
    report = TestReport(passed=0, failed=1, failures=failures, duration=0.1)
    text = format_audit_test_text(report)
    # Should not crash; line exists
    failure_lines = [line for line in text.splitlines() if line.startswith("\u2717")]
    assert len(failure_lines) == 1


def test_zero_tests_collected():
    report = TestReport(passed=0, failed=0, duration=0.0, coverage=50.0)
    text = format_audit_test_text(report)
    assert "0 passed" in text
    assert "\u2717" not in text


def test_coverage_exactly_95_not_shown():
    report = TestReport(
        passed=5,
        failed=0,
        coverage=95.0,
        coverage_by_file={"b.py": 95.0},
        duration=0.5,
    )
    text = format_audit_test_text(report)
    # 95.0 is NOT below threshold → no per-file line
    file_lines = [line for line in text.splitlines()[1:] if "b.py" in line]
    assert len(file_lines) == 0


# ---------------------------------------------------------------------------
# Wiring: AuditTestTool.execute() sets ToolResult.text
# ---------------------------------------------------------------------------


def test_execute_returns_text_in_toolresult(tmp_path):
    report = TestReport(passed=3, failed=0, coverage=99.0, duration=0.5)
    with patch("axm_audit.core.test_runner.run_tests", return_value=report):
        from axm_audit.tools.audit_test import AuditTestTool

        tool = AuditTestTool()
        result = tool.execute(path=str(tmp_path))

    assert result.success is True
    assert result.data is not None
    assert result.text is not None
    assert "audit_test" in result.text
    assert "3 passed" in result.text
