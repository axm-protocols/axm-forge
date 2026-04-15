from __future__ import annotations

from typing import Any

from axm_audit.core.test_runner import TestReport
from axm_audit.tools.audit_test_text import _build_coverage_section, _build_header


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
    header = _build_header(report)
    assert "cov 91.9%" in header


def test_coverage_section_rounded() -> None:
    """Per-file coverage in cov< section is rounded to 1 decimal."""
    report = _make_report(coverage_by_file={"src/foo.py": 88.932806})
    lines = _build_coverage_section(report)
    assert len(lines) == 1
    assert "foo.py 88.9%" in lines[0]


def test_coverage_exact_boundary() -> None:
    """Exact float like 95.0 renders as 95.0% (1 decimal)."""
    report = _make_report(coverage=95.0)
    header = _build_header(report)
    assert "cov 95.0%" in header


# --- Edge cases ---


def test_coverage_perfect() -> None:
    """100.0 coverage renders as cov 100.0%."""
    report = _make_report(coverage=100.0)
    header = _build_header(report)
    assert "cov 100.0%" in header


def test_coverage_zero() -> None:
    """0.0 coverage renders as cov 0.0%."""
    report = _make_report(coverage=0.0)
    header = _build_header(report)
    assert "cov 0.0%" in header
