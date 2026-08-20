"""Split from ``test_subprocess_runner_layouts.py``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit.core.test_runner import build_test_report, parse_json_report


class TestBuildTestReport:
    """Tests for the extracted _build_test_report helper."""

    def test_build_test_report_helper(self, tmp_path: Path) -> None:
        """Tests that _build_test_report correctly constructs a TestReport."""
        from axm_audit.core.test_runner import build_test_report

        report_data = {
            "summary": {
                "passed": 2,
                "failed": 1,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
            },
            "duration": 1.5,
            "tests": [
                {
                    "outcome": "failed",
                    "nodeid": "test_foo.py::test_bar",
                    "call": {
                        "crash": {
                            "message": "AssertionError: False is not True",
                            "path": "test_foo.py",
                            "lineno": 10,
                        },
                        "longrepr": "Traceback...\nAssertionError",
                    },
                }
            ],
        }

        per_file_cov = {"src/foo.py": 80.0}

        report = build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file_cov,
            mode="failures",
            last_coverage=None,
        )

        assert report.passed == 2
        assert report.failed == 1
        assert report.coverage == 85.0
        assert report.failures is not None
        assert len(report.failures) == 1
        assert report.failures[0].test == "test_foo.py::test_bar"


_COVERAGE_THRESHOLD_OUTPUT = (
    "---------- coverage: platform darwin, python 3.12.4 ----------\n"
    "TOTAL                          120     34    71%\n"
    "FAIL Required test coverage of 85% not reached. "
    "Total coverage: 71.42%\n"
)


def _cause_code(cause: object) -> object:
    """Return the classification code, tolerating an enum or a plain string."""
    code = getattr(cause, "code", cause)
    return getattr(code, "value", code)


def _cause_excerpt(cause: object) -> str:
    """Return the first non-empty textual excerpt carried by the cause."""
    for attr in ("excerpt", "evidence", "detail", "output_excerpt", "stderr_excerpt"):
        value = getattr(cause, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _parsed_report(tmp_path: Path, *, passed: int, failed: int) -> dict[str, object]:
    """Write a valid pytest JSON report on disk and parse it back."""
    tests: list[dict[str, object]] = [
        {"nodeid": f"tests/test_ex.py::test_pass_{index}", "outcome": "passed"}
        for index in range(passed)
    ]
    tests.extend(
        {
            "nodeid": f"tests/test_ex.py::test_fail_{index}",
            "outcome": "failed",
            "call": {"longrepr": f"AssertionError: {index}"},
        }
        for index in range(failed)
    )
    payload = {
        "summary": {
            "passed": passed,
            "failed": failed,
            "error": 0,
            "skipped": 0,
            "warnings": 0,
            "collected": passed + failed,
        },
        "tests": tests,
        "duration": 0.5,
    }
    report_file = tmp_path / "pytest-report.json"
    report_file.write_text(json.dumps(payload))
    return parse_json_report(report_file)


@pytest.mark.integration
def test_build_test_report_attaches_the_coverage_threshold_cause(
    tmp_path: Path,
) -> None:
    """AC2: a suite with zero failure failing only the coverage gate.

    The JSON report parses cleanly with no failure, no error and a non-zero
    collected count, yet pytest exited 1 because of the pytest-cov threshold:
    the captured output is the only evidence, and it must be classified.
    """
    report_data = _parsed_report(tmp_path, passed=3, failed=0)

    report = build_test_report(
        report_data=report_data,
        total_cov=71.42,
        per_file_cov={"src/a.py": 71.42},
        return_code=1,
        stdout=_COVERAGE_THRESHOLD_OUTPUT,
        stderr="",
    )

    assert report.non_test_cause is not None
    assert _cause_code(report.non_test_cause) == "coverage_threshold"
    assert _cause_excerpt(report.non_test_cause)


@pytest.mark.integration
def test_build_test_report_leaves_the_cause_none_for_green_and_failed_runs(
    tmp_path: Path,
) -> None:
    """AC3: a green run and a red-by-test-failures run carry no cause."""
    green = build_test_report(
        report_data=_parsed_report(tmp_path, passed=4, failed=0),
        total_cov=92.0,
        per_file_cov={"src/a.py": 92.0},
        return_code=0,
        stdout="4 passed in 0.50s\n",
        stderr="",
    )
    red = build_test_report(
        report_data=_parsed_report(tmp_path, passed=2, failed=2),
        total_cov=92.0,
        per_file_cov={"src/a.py": 92.0},
        return_code=1,
        stdout="2 failed, 2 passed in 0.50s\n",
        stderr="",
    )

    assert green.non_test_cause is None
    assert red.non_test_cause is None
    assert red.failed == 2
