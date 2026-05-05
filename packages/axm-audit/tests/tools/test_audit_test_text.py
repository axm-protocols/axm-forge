from __future__ import annotations

from typing import Any

from axm_audit.core.test_runner import TestReport
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


# --- Unit tests ---


def test_header_coverage_rounded() -> None:
    """Coverage with many decimals is rounded to 1 decimal in header."""
    report = _make_report(coverage=91.89025)
    text = format_audit_test_text(report)
    assert "cov 91.9%" in text


def test_coverage_section_rounded() -> None:
    """Per-file coverage in cov< section is rounded to 1 decimal."""
    report = _make_report(coverage_by_file={"src/foo.py": 88.932806})
    text = format_audit_test_text(report)
    assert "cov<" in text
    assert "foo.py 88.9%" in text


def test_coverage_exact_boundary() -> None:
    """Exact float like 95.0 renders as 95.0% (1 decimal)."""
    report = _make_report(coverage=95.0)
    text = format_audit_test_text(report)
    assert "cov 95.0%" in text


# --- Edge cases ---


def test_coverage_perfect() -> None:
    """100.0 coverage renders as cov 100.0%."""
    report = _make_report(coverage=100.0)
    text = format_audit_test_text(report)
    assert "cov 100.0%" in text


def test_coverage_zero() -> None:
    """0.0 coverage renders as cov 0.0%."""
    report = _make_report(coverage=0.0)
    text = format_audit_test_text(report)
    assert "cov 0.0%" in text
