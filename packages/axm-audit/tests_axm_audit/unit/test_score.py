"""Unit tests for the single-source score/grade serialization."""

from __future__ import annotations

import pytest

from axm_audit.models.results import AuditResult, CheckResult
from axm_audit.score import (
    ScoreIncalculableError,
    _has_scored_signal,
    resolve_score_grade,
    score_grade_or_none,
)

_GRADES = {"A", "B", "C", "D", "F"}


def _all_not_applicable_result() -> AuditResult:
    """A scored-category check whose metric is not-applicable (score=None)."""
    return AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="not applicable",
                category="lint",
                score=None,
            )
        ]
    )


def test_all_not_applicable_resolves_to_na_not_zero_f() -> None:
    """AC2: an all-not-applicable result surfaces N/A, never a misleading 0/F.

    ``quality_score`` is ``None`` because every scored-category check is
    not-applicable (dropped by ``collect_category_scores``). The tolerant
    surface returns ``(None, None)`` and the strict surface fails loud instead
    of assuming ``0.0``/``"F"``.
    """
    result = _all_not_applicable_result()
    assert result.quality_score is None  # precondition

    assert score_grade_or_none(result) == (None, None)
    with pytest.raises(ScoreIncalculableError):
        resolve_score_grade(result)


def test_mixed_measured_and_na_matches_absent_category_parity() -> None:
    """AC1: a mixed measured + all-N/A category scores exactly as if the N/A
    category were simply absent (weight-normalisation parity)."""
    mixed = AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="ok",
                category="lint",
                score=90,
            ),
            CheckResult(
                rule_id="QUALITY_SECURITY",
                passed=True,
                message="not applicable",
                category="security",
                score=None,
            ),
        ]
    )
    without_na = AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="ok",
                category="lint",
                score=90,
            )
        ]
    )

    assert resolve_score_grade(mixed) == resolve_score_grade(without_na)


def test_na_resolution_is_driven_by_quality_score_none_signal() -> None:
    """AC4: the N/A verdict is driven by ``quality_score is None`` even though a
    scored signal is present — not by a separate re-implemented predicate."""
    result = _all_not_applicable_result()

    # A scored-category check exists (scored signal present) ...
    assert _has_scored_signal(result) is True
    # ... yet the weight-normalising score is None (all metrics not-applicable).
    assert result.quality_score is None
    # ... so serialization resolves to N/A, not 0/F.
    assert score_grade_or_none(result) == (None, None)


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
    """AC3: a measured scored check flows through verbatim with its grade
    (no regression on the happy path)."""
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
