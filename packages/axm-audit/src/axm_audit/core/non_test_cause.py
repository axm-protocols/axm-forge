"""Name the cause of a pytest red that no test failure explains.

A run that collects tests, reports zero ``failed`` and zero ``errors`` yet
exits non-zero has a cause the counters cannot name: a coverage threshold, a
usage error, an empty collection, an interruption, an internal error, or a
plugin blowing up at session teardown. This module classifies that cause from
the exit code and the captured output alone -- no I/O, no clock, no randomness
-- so a report can explain the red without re-running pytest by hand.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

__all__ = ["NonTestCause", "classify_non_test_cause"]

# How much of a failed subprocess's captured output is quoted in a diagnostic.
# A failed uv resolution runs to several kilobytes; the cause is in its opening
# lines, so the head is kept and the rest dropped. This is the CANONICAL
# definition of the budget: ``axm_audit.core.test_runner`` imports it (and
# ``_truncate_excerpt``) rather than duplicating the discipline.
_STDERR_EXCERPT_CHARS = 1200

_TRUNCATION_MARKER = "\n[... stderr truncated]"

NonTestCauseCode = Literal[
    "coverage_threshold",
    "usage_error",
    "no_tests_collected",
    "interrupted",
    "internal_error",
    "plugin_teardown_failure",
    "unknown",
]

# Documented pytest exit codes that already name their own cause.
_EXIT_CODE_CAUSES: dict[int, tuple[NonTestCauseCode, str]] = {
    2: ("interrupted", "pytest was interrupted before the run completed"),
    3: ("internal_error", "pytest raised an internal error"),
    4: ("usage_error", "pytest was invoked with a usage error"),
    5: ("no_tests_collected", "pytest collected no test at all"),
}

_COVERAGE_PATTERN = re.compile(
    r"required test coverage of ([\d.]+)% not reached",
    re.IGNORECASE,
)

_TEARDOWN_MARKERS = (
    "error during session teardown",
    "errors during session teardown",
    "pytest_sessionfinish",
)


def _truncate_excerpt(text: str) -> str:
    """Return *text* stripped and bounded to :data:`_STDERR_EXCERPT_CHARS`.

    The single truncation discipline of the package: an over-long excerpt keeps
    its head (where the cause lives) and ends with the truncation marker.
    """
    stripped = text.strip()
    if len(stripped) <= _STDERR_EXCERPT_CHARS:
        return stripped
    return stripped[:_STDERR_EXCERPT_CHARS] + _TRUNCATION_MARKER


# ``type: ignore[explicit-any]``: the pydantic mypy plugin synthesizes
# ``__init__(**data: Any)``, which strict ``disallow_any_explicit`` rejects on the
# class line. Same waiver as models/results.py and doc_gate/findings.py.
class NonTestCause(BaseModel):  # type: ignore[explicit-any]
    """Machine-readable cause of a red no test failure accounts for."""

    code: NonTestCauseCode
    """Stable identifier of the cause, safe to branch on."""

    summary: str
    """One-line human explanation, quoting the decisive figure when there is one."""

    excerpt: str
    """Bounded head of the captured subprocess output backing the verdict."""


def _coverage_cause(captured: str) -> NonTestCause | None:
    """Classify a pytest-cov threshold message, if the output carries one."""
    match = _COVERAGE_PATTERN.search(captured)
    if match is None:
        return None
    return NonTestCause(
        code="coverage_threshold",
        summary=f"required test coverage of {match.group(1)}% not reached",
        excerpt=_truncate_excerpt(captured),
    )


def _teardown_cause(captured: str) -> NonTestCause | None:
    """Classify a plugin failing at session teardown, if the output shows one."""
    lowered = captured.lower()
    if not any(marker in lowered for marker in _TEARDOWN_MARKERS):
        return None
    return NonTestCause(
        code="plugin_teardown_failure",
        summary="a pytest plugin failed during session teardown",
        excerpt=_truncate_excerpt(captured),
    )


def classify_non_test_cause(
    *,
    return_code: int,
    failed: int,
    errors: int,
    stdout: str,
    stderr: str,
) -> NonTestCause | None:
    """Name the non-test cause of a pytest exit, or ``None`` when there is none.

    Returns ``None`` for a green exit and for a red the test counters already
    explain (``failed`` or ``errors`` non-zero) -- there is nothing left to
    diagnose. Otherwise the exit code is dispatched first (it is authoritative
    when pytest sets it), then the captured output is pattern-matched for the
    ambiguous exit 1. Classification is fail-open: an unrecognised output is
    reported as ``unknown`` carrying its excerpt, never raised and never
    silently dropped.
    """
    if return_code == 0 or failed > 0 or errors > 0:
        return None

    captured = f"{stdout}\n{stderr}"
    known = _EXIT_CODE_CAUSES.get(return_code)
    if known is not None:
        code, summary = known
        return NonTestCause(
            code=code,
            summary=summary,
            excerpt=_truncate_excerpt(captured) or summary,
        )

    coverage = _coverage_cause(captured)
    if coverage is not None:
        return coverage

    teardown = _teardown_cause(captured)
    if teardown is not None:
        return teardown

    fallback = f"pytest exited with code {return_code} without any reported failure"
    return NonTestCause(
        code="unknown",
        summary=fallback,
        excerpt=_truncate_excerpt(captured) or fallback,
    )
