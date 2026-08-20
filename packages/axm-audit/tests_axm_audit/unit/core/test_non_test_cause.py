"""Unit tests for axm_audit.core.non_test_cause (pure classifier, no I/O)."""

from __future__ import annotations

import subprocess

import pytest

from axm_audit.core.non_test_cause import (
    _STDERR_EXCERPT_CHARS,
    NonTestCause,
    _truncate_excerpt,
    classify_non_test_cause,
)

_TRUNCATION_MARKER = "\n[... stderr truncated]"

_COVERAGE_STDOUT = (
    "FAIL Required test coverage of 85% not reached. Total coverage: 72.10%"
)

_PLUGIN_TEARDOWN_STDERR = (
    "Traceback (most recent call last):\n"
    '  File "/venv/lib/_pytest/runner.py", line 120, in pytest_sessionfinish\n'
    "    checker.teardown()\n"
    "RuntimeError: checker plugin exploded\n"
    "error during session teardown\n"
)


def test_returns_none_on_green_exit_and_on_red_already_explained() -> None:
    """AC1: nothing to classify on success, nor when the tests own the red."""
    green = classify_non_test_cause(
        return_code=0, failed=0, errors=0, stdout="", stderr=""
    )
    with_failures = classify_non_test_cause(
        return_code=1, failed=2, errors=0, stdout="boom", stderr=""
    )
    with_errors = classify_non_test_cause(
        return_code=1, failed=0, errors=1, stdout="", stderr="boom"
    )

    assert green is None
    assert with_failures is None
    assert with_errors is None


@pytest.mark.parametrize(
    ("return_code", "expected_code"),
    [
        (2, "interrupted"),
        (3, "internal_error"),
        (4, "usage_error"),
        (5, "no_tests_collected"),
    ],
)
def test_maps_each_pytest_exit_code_to_its_named_cause(
    return_code: int, expected_code: str
) -> None:
    """AC2: exit codes 2/3/4/5 dispatch to their documented machine code."""
    cause = classify_non_test_cause(
        return_code=return_code, failed=0, errors=0, stdout="", stderr=""
    )

    assert isinstance(cause, NonTestCause)
    assert cause.code == expected_code


def test_classifies_coverage_threshold_message_on_exit_one() -> None:
    """AC3: a pytest-cov threshold red is named and quotes its threshold."""
    cause = classify_non_test_cause(
        return_code=1, failed=0, errors=0, stdout=_COVERAGE_STDOUT, stderr=""
    )

    assert cause is not None
    assert cause.code == "coverage_threshold"
    assert "85" in cause.summary
    assert cause.excerpt != ""


def test_classifies_plugin_failure_at_session_teardown() -> None:
    """AC4: a plugin blowing up at session teardown is named, not swallowed."""
    cause = classify_non_test_cause(
        return_code=1,
        failed=0,
        errors=0,
        stdout="",
        stderr=_PLUGIN_TEARDOWN_STDERR,
    )

    assert cause is not None
    assert cause.code == "plugin_teardown_failure"
    assert cause.excerpt != ""


def test_unrecognised_output_fails_open_to_unknown_with_an_excerpt() -> None:
    """AC4: an unrecognised red yields ``unknown`` + excerpt, never a raise."""
    cause = classify_non_test_cause(
        return_code=1,
        failed=0,
        errors=0,
        stdout="sortie totalement non reconnue",
        stderr="",
    )

    assert cause is not None
    assert cause.code == "unknown"
    assert cause.excerpt != ""


def test_excerpt_is_bounded_by_the_shared_truncation_budget() -> None:
    """AC5: a 10x oversized output is truncated and keeps the marker."""
    cause = classify_non_test_cause(
        return_code=1,
        failed=0,
        errors=0,
        stdout="x" * (10 * _STDERR_EXCERPT_CHARS),
        stderr="",
    )

    assert cause is not None
    assert len(cause.excerpt) <= _STDERR_EXCERPT_CHARS + len(_TRUNCATION_MARKER)
    assert cause.excerpt.endswith(_TRUNCATION_MARKER)


def test_truncation_constant_and_helper_are_shared_with_subprocess_failure() -> None:
    """AC6: one canonical constant/helper, routed by _subprocess_failure."""
    from axm_audit.core import non_test_cause, test_runner
    from axm_audit.core.test_runner import _subprocess_failure

    assert test_runner._STDERR_EXCERPT_CHARS is non_test_cause._STDERR_EXCERPT_CHARS
    assert test_runner._truncate_excerpt is _truncate_excerpt

    stderr = (
        "HEAD-MARKER resolution failed\n"
        + ("filler line of subprocess noise\n" * _STDERR_EXCERPT_CHARS)
        + "TAIL-MARKER last line of the dump"
    )
    completed = subprocess.CompletedProcess(
        args=["pytest"], returncode=1, stdout="", stderr=stderr
    )

    enriched = _subprocess_failure(ValueError("no report"), completed)
    message = str(enriched)

    assert "HEAD-MARKER" in message
    assert "TAIL-MARKER" not in message
    assert _TRUNCATION_MARKER in message
