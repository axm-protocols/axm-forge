from __future__ import annotations

from typing import Any

import pytest

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
