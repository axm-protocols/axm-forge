"""Integration: run_tests() ignores deprecated mode argument (uses tmp_path)."""

from __future__ import annotations

import pytest

from axm_audit.core.test_runner import run_tests


@pytest.mark.integration
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
