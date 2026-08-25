from __future__ import annotations

from typing import Any

import pytest

from axm_audit.core.non_test_cause import (
    _STDERR_EXCERPT_CHARS,
    _TRUNCATION_MARKER,
    classify_non_test_cause,
)
from axm_audit.core.test_runner import (
    FailureDetail,
    NonTestCauseDetail,
    TestReport,
    build_test_report,
)
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


@pytest.mark.parametrize(
    ("metadata", "expected_success", "expected_fragments"),
    [
        pytest.param(
            {
                "pytest_return_code": 0,
                "collected": 3,
                "target_statuses": [
                    {"target": "tests/test_many.py", "status": "validated"}
                ],
                "verdict": True,
            },
            True,
            ("3 collected",),
            id="success",
        ),
        pytest.param(
            {
                "pytest_return_code": 0,
                "collected": 0,
                "target_statuses": [],
                "verdict": False,
            },
            False,
            ("0 collected",),
            id="zero_collection",
        ),
        pytest.param(
            {
                "pytest_return_code": 0,
                "collected": 4,
                "target_statuses": [
                    {"target": "tests/test_empty.py", "status": "omitted"}
                ],
                "verdict": False,
            },
            False,
            ("tests/test_empty.py", "omitted"),
            id="invalid_target",
        ),
        pytest.param(
            {
                "pytest_return_code": 3,
                "collected": 1,
                "target_statuses": [],
                "verdict": False,
            },
            False,
            ("pytest exit 3",),
            id="non_success_exit",
        ),
    ],
)
def test_text_uses_the_structured_verdict(
    metadata: dict[str, Any],
    expected_success: bool,
    expected_fragments: tuple[str, ...],
) -> None:
    """AC6: text color and evidence consume the report's single verdict."""
    report = _make_report(**metadata)
    text = format_audit_test_text(report)

    assert text.startswith("audit_test | ✅" if expected_success else "audit_test | ❌")
    for fragment in expected_fragments:
        assert fragment in text


def test_text_rendering_is_independent_of_case_count() -> None:
    """AC4: zero and five hundred cases render to byte-identical compact text."""
    empty = _make_report()
    tests = [
        {
            "nodeid": f"tests/unit/test_many.py::test_case[{index}]",
            "outcome": "passed",
        }
        for index in range(500)
    ]
    populated = build_test_report(
        report_data={
            "summary": {
                "passed": 1,
                "failed": 0,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
            },
            "tests": tests,
            "duration": 0.5,
        },
        total_cov=None,
        per_file_cov={},
        include_cases=True,
    )

    assert len(populated.cases) == 500
    assert format_audit_test_text(populated) == format_audit_test_text(empty)


# --- Non-test cause rendering ---


_COVERAGE_STDOUT = (
    "FAIL Required test coverage of 85% not reached. Total coverage: 42.31%"
)
_COVERAGE_SUMMARY = "required test coverage of 85% not reached"


def _make_cause_detail(stdout: str) -> NonTestCauseDetail:
    """Project the classifier's own verdict on *stdout* into a report field."""
    cause = classify_non_test_cause(
        return_code=1,
        failed=0,
        errors=0,
        stdout=stdout,
        stderr="",
    )
    assert cause is not None
    detail = NonTestCauseDetail.from_cause(cause)
    assert detail is not None
    return detail


def test_non_test_cause_renders_right_after_the_pytest_exit_line() -> None:
    """AC1: cause code and summary sit on the line after ``pytest exit N``."""
    report = _make_report(
        failed=0,
        errors=0,
        pytest_return_code=1,
        non_test_cause=_make_cause_detail(_COVERAGE_STDOUT),
    )

    lines = format_audit_test_text(report).splitlines()
    exit_index = next(
        index for index, line in enumerate(lines) if "pytest exit 1" in line
    )
    assert len(lines) > exit_index + 1
    cause_line = lines[exit_index + 1]

    assert "coverage_threshold" in cause_line
    assert _COVERAGE_SUMMARY in cause_line


def test_rendered_cause_excerpt_keeps_the_single_truncation_budget() -> None:
    """AC2: the excerpt follows the cause line and is never re-truncated."""
    detail_lines = "\n".join(f"detail line {index}" for index in range(400))
    detail = _make_cause_detail(f"{_COVERAGE_STDOUT}\n{detail_lines}")
    assert detail.excerpt.endswith(_TRUNCATION_MARKER)

    report = _make_report(
        failed=0,
        errors=0,
        pytest_return_code=1,
        non_test_cause=detail,
    )
    text = format_audit_test_text(report)

    assert "coverage_threshold" in text
    assert _COVERAGE_STDOUT in text
    assert text.index(_COVERAGE_STDOUT) > text.index("coverage_threshold")

    tail = text[text.index(_COVERAGE_STDOUT) :]
    rendered = "\n".join(line.strip() for line in tail.splitlines())
    assert _TRUNCATION_MARKER.strip() in rendered
    assert len(rendered) <= _STDERR_EXCERPT_CHARS + len(_TRUNCATION_MARKER)
