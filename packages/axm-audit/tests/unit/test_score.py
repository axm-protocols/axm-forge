"""Unit tests for the single-source score/grade serialization."""

from __future__ import annotations

import pytest

from axm_audit.models.results import AuditResult, CheckResult
from axm_audit.score import (
    ScoreIncalculableError,
    resolve_score_grade,
    score_grade_or_none,
)

_GRADES = {"A", "B", "C", "D", "F"}


def _unmeasured_result() -> AuditResult:
    """A scored-category check whose metric came back unmeasured (score=None)."""
    return AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="unmeasured",
                category="lint",
                score=None,
            )
        ]
    )


def test_serialized_score_numeric_with_unmeasured_metrics() -> None:
    """AC1/AC3: unmeasured scored metrics still yield a numeric score + grade.

    ``quality_score`` is ``None`` (the single metric is unmeasured) yet the
    serialization source assumes it and returns a concrete number, so no
    ``.score`` is ever dropped on the success path.
    """
    assert _unmeasured_result().quality_score is None  # precondition

    score, grade = resolve_score_grade(_unmeasured_result())

    assert isinstance(score, int | float)
    assert grade in _GRADES


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(AuditResult(checks=[]), id="no_checks"),
        pytest.param(
            AuditResult(
                checks=[
                    CheckResult(
                        rule_id="STRUCT_LAYOUT",
                        passed=True,
                        message="ok",
                        category="structure",
                    )
                ]
            ),
            id="unscored_category_only",
        ),
    ],
)
def test_incalculable_score_raises_fail_loud(result: AuditResult) -> None:
    """AC2: no scored signal → explicit error, never a silent partial payload."""
    with pytest.raises(ScoreIncalculableError):
        resolve_score_grade(result)


def test_tolerant_variant_returns_none_instead_of_raising() -> None:
    """The lax surface returns ``(None, None)`` rather than failing loud."""
    assert score_grade_or_none(AuditResult(checks=[])) == (None, None)


def test_computed_score_passes_through_with_matching_grade() -> None:
    """A measured scored check flows through verbatim with its derived grade."""
    result = AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="ok",
                category="lint",
                score=95,
            )
        ]
    )

    score, grade = resolve_score_grade(result)

    assert score == 95.0
    assert grade == "A"
