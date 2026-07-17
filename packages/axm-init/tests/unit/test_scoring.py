"""Unit tests for the category scoring routine and its verdict model.

Covers the three scoring states:

* N/A          — summed weight 0 -> not-applicable verdict, no numeric grade.
* real zero     — weight > 0, all checks fail -> genuine 0/100 Grade F.
* normal        — weight > 0, checks pass -> positive score, applicable.
"""

from __future__ import annotations

from axm_init.models.check import CategoryScore, CheckResult, Grade


def _check(name: str, *, passed: bool, weight: int) -> CheckResult:
    """Build a minimal CheckResult for scoring."""
    return CheckResult(
        name=name,
        category="cat",
        passed=passed,
        weight=weight,
        message="m",
        details=[],
        fix="",
    )


class TestNotApplicable:
    """AC1 — zero total weight yields a not-applicable verdict."""

    def test_zero_weight_is_not_applicable(self) -> None:
        verdict = CategoryScore.from_checks("cat", [_check("x", passed=True, weight=0)])
        assert verdict.applicable is False
        assert verdict.not_applicable is True

    def test_zero_weight_has_no_numeric_grade(self) -> None:
        verdict = CategoryScore.from_checks(
            "cat", [_check("x", passed=False, weight=0)]
        )
        assert verdict.score is None
        assert verdict.grade is None


class TestRealZero:
    """AC2 — positive weight, all failing, yields a real 0/100 Grade F."""

    def test_all_failing_scores_real_zero(self) -> None:
        verdict = CategoryScore.from_checks(
            "cat",
            [
                _check("a", passed=False, weight=5),
                _check("b", passed=False, weight=3),
            ],
        )
        assert verdict.score == 0
        assert verdict.grade == Grade.F
        assert verdict.applicable is True


class TestApplicabilityFlag:
    """AC3 — the flag distinguishes N/A from a real zero."""

    def test_na_and_real_zero_differ_on_flag(self) -> None:
        na = CategoryScore.from_checks("cat", [_check("x", passed=True, weight=0)])
        real_zero = CategoryScore.from_checks(
            "cat", [_check("y", passed=False, weight=5)]
        )
        assert na.applicable != real_zero.applicable
        assert na.applicable is False
        assert real_zero.applicable is True


class TestNormalScore:
    """AC2 regression — passing checks score normally."""

    def test_passing_checks_score_normally(self) -> None:
        verdict = CategoryScore.from_checks(
            "cat",
            [
                _check("a", passed=True, weight=8),
                _check("b", passed=False, weight=2),
            ],
        )
        assert verdict.score == 80
        assert verdict.grade != Grade.F
        assert verdict.applicable is True
