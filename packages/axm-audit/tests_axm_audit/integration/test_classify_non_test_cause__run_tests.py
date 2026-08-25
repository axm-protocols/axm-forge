"""Integration coverage: a real red run explains its own non-test cause."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.test_runner import run_tests
from axm_audit.tools.audit_test_text import format_audit_test_text


def _write_cov_threshold_project(root: Path) -> None:
    """Write a project whose green suite still misses its coverage gate."""
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'addopts = ["--cov=covpkg", "--cov-fail-under=100"]\n',
        encoding="utf-8",
    )
    (root / "covpkg.py").write_text(
        "def classify(value: int) -> str:\n"
        "    if value < 0:\n"
        '        return "negative"\n'
        '    return "positive"\n',
        encoding="utf-8",
    )
    (root / "test_covpkg.py").write_text(
        "from covpkg import classify\n\n"
        "def test_classify_positive():\n"
        '    assert classify(1) == "positive"\n',
        encoding="utf-8",
    )


@pytest.mark.integration
def test_coverage_threshold_red_is_explainable_from_the_report(
    tmp_path: Path,
) -> None:
    """AC3: a real coverage-threshold red names its cause in the rendered text."""
    _write_cov_threshold_project(tmp_path)

    report = run_tests(tmp_path, stop_on_first=False)
    text = format_audit_test_text(report)

    assert report.verdict is False
    assert report.non_test_cause is not None
    excerpt_lines = [
        line for line in report.non_test_cause.excerpt.splitlines() if line.strip()
    ]
    assert excerpt_lines
    assert "coverage_threshold" in text
    assert report.non_test_cause.summary in text
    assert any(line in text for line in excerpt_lines)
