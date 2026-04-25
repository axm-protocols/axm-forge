"""Public-API tests for ``AuditResult.quality_score`` (replaces private
``_collect_category_scores`` import in ``tests/test_quality_score.py``)."""

from __future__ import annotations

from axm_audit.models import AuditResult, CheckResult


def _check(
    rule_id: str, category: str, score: int, *, passed: bool = True
) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=passed,
        message=f"{rule_id}: {score}/100",
        category=category,
        details={"score": score},
    )


def test_audit_result_score_aggregates_by_category():
    """AC4: ``quality_score`` averages within a category, then weights across.

    Weights: lint=20, type=15, complexity=15, security=10, deps=10,
    testing=15, architecture=10, practices=5.
    """
    checks = [
        _check("lint_a", "lint", 100),
        _check("lint_b", "lint", 80),
        _check("sec_a", "security", 60, passed=False),
    ]
    result = AuditResult(checks=checks)

    # Lint average = 90 (weight 20); security average = 60 (weight 10).
    # Weighted total = 90*20 + 60*10 = 2400; weight_sum = 30; score = 80.0.
    assert result.quality_score is not None
    assert abs(result.quality_score - 80.0) < 0.5


def test_audit_result_score_returns_none_with_no_scored_checks():
    """AC4: with no scored checks, ``quality_score`` is None (and grade None)."""
    result = AuditResult(checks=[])
    assert result.quality_score is None
    assert result.grade is None


def test_audit_result_score_normalizes_partial_categories():
    """AC4: a single-category audit is not penalized for missing categories."""
    checks = [_check("lint_a", "lint", 90)]
    result = AuditResult(checks=checks)
    assert result.quality_score == 90.0
