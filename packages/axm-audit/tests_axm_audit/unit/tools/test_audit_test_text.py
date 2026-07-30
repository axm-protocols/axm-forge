from __future__ import annotations

from typing import Any

import pytest

from axm_audit.core.test_runner import FailureDetail, TestReport
from axm_audit.tools.audit_test_text import format_audit_test_text


def _make_report(**kwargs: Any) -> TestReport:
    defaults: dict[str, Any] = {
        "passed": 1,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "duration": 0.5,
        "coverage": None,
        "coverage_by_file": None,
    }
    defaults.update(kwargs)
    return TestReport(**defaults)


def _make_failure(**kwargs: Any) -> FailureDetail:
    defaults: dict[str, Any] = {
        "test": "tests/unit/test_x.py::test_one",
        "error_type": "AssertionError",
        "message": "expected 1 got 2",
        "file": "tests/unit/test_x.py",
        "line": 42,
        "traceback": "",
    }
    defaults.update(kwargs)
    return FailureDetail(**defaults)


# --- Unit tests ---


@pytest.mark.parametrize(
    ("coverage", "expected"),
    [
        pytest.param(91.89025, "cov 91.9%", id="header_coverage_rounded"),
        pytest.param(95.0, "cov 95.0%", id="coverage_exact_boundary"),
        pytest.param(100.0, "cov 100.0%", id="coverage_perfect"),
        pytest.param(0.0, "cov 0.0%", id="coverage_zero"),
    ],
)
def test_coverage_header_rendering(coverage: float, expected: str) -> None:
    report = _make_report(coverage=coverage)
    text = format_audit_test_text(report)
    assert expected in text


def test_coverage_section_rounded() -> None:
    """Per-file coverage in cov< section is rounded to 1 decimal."""
    report = _make_report(coverage_by_file={"src/foo.py": 88.932806})
    text = format_audit_test_text(report)
    assert "cov<" in text
    assert "foo.py 88.9%" in text


def test_header_green_icon_when_no_failures() -> None:
    """Header shows the green check when failed + errors == 0."""
    text = format_audit_test_text(_make_report())
    assert text.startswith("audit_test | ✅")


def test_header_red_icon_when_failed_present() -> None:
    """Header shows the red cross when failed > 0.

    Also exercises the optional ``errors`` / ``skipped`` count fragments
    which are omitted from the header when zero.
    """
    report = _make_report(passed=2, failed=1, errors=1, skipped=3)
    text = format_audit_test_text(report)
    header = text.splitlines()[0]
    assert header.startswith("audit_test | ❌")
    assert "2 passed" in header
    assert "1 failed" in header
    assert "1 errors" in header
    assert "3 skipped" in header


def test_failure_block_emitted_with_location_and_truncation() -> None:
    """Failure rendering shows the node id, location, error_type, message."""
    report = _make_report(
        failed=1,
        failures=[
            _make_failure(
                test="tests/unit/test_x.py::test_one",
                file="tests/unit/test_x.py",
                line=42,
                error_type="AssertionError",
                message="boom",
                traceback="line A\nline B",
            )
        ],
    )
    text = format_audit_test_text(report)
    assert "tests/unit/test_x.py::test_one (test_x.py:42)" in text
    assert "AssertionError: boom" in text
    assert "    line A" in text
    assert "    line B" in text


def test_failure_block_truncates_long_nodeid() -> None:
    """Node IDs longer than the threshold are abbreviated with ``...``."""
    long_id = "tests/unit/test_x.py::" + "x" * 200
    report = _make_report(
        failed=1,
        failures=[_make_failure(test=long_id, file="", traceback="")],
    )
    text = format_audit_test_text(report)
    # The line displayed should be shorter than the original and end with ...
    failure_line = next(line for line in text.splitlines() if "✗" in line)
    assert "..." in failure_line
    assert long_id not in failure_line


def test_coverage_section_absent_when_no_per_file_data() -> None:
    """No ``cov<`` line when ``coverage_by_file`` is None."""
    text = format_audit_test_text(_make_report(coverage=92.0))
    assert "cov<" not in text


def test_coverage_section_absent_when_all_files_at_threshold() -> None:
    """All files >= threshold -> no ``cov<`` line emitted.

    Threshold is 95.0; entries at exactly 95.0 are NOT shown (the
    formatter uses strict ``<``).
    """
    report = _make_report(coverage_by_file={"src/a.py": 95.0, "src/b.py": 99.0})
    text = format_audit_test_text(report)
    assert "cov<" not in text
