"""Public-API tests for ``AuditResult.quality_score``.

Property-based tests that do not depend on the exact weights table.
"""

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


def test_audit_result_score_aggregates_within_category() -> None:
    """Multiple checks in one category are averaged before weighting.

    With a single category, weights cancel out and the composite equals
    the category's mean — we don't need to know the weight to assert this.
    """
    checks = [
        _check("lint_a", "lint", 100),
        _check("lint_b", "lint", 80),
    ]
    result = AuditResult(checks=checks)
    assert result.quality_score is not None
    # avg(100, 80) = 90
    assert abs(result.quality_score - 90.0) < 0.1


def test_audit_result_score_combines_categories_within_bounds() -> None:
    """Combining categories yields a score in [min(cat_avg), max(cat_avg)]."""
    checks = [
        _check("lint_a", "lint", 100),
        _check("lint_b", "lint", 80),  # lint mean = 90
        _check("sec_a", "security", 60, passed=False),  # security mean = 60
    ]
    result = AuditResult(checks=checks)
    assert result.quality_score is not None
    # Score is a weighted average of 90 and 60 → must lie in [60, 90].
    assert 60.0 <= result.quality_score <= 90.0


def test_audit_result_score_returns_none_with_no_scored_checks() -> None:
    result = AuditResult(checks=[])
    assert result.quality_score is None
    assert result.grade is None


def test_audit_result_score_normalizes_partial_categories() -> None:
    """A single-category audit is not penalized for missing categories."""
    checks = [_check("lint_a", "lint", 90)]
    result = AuditResult(checks=checks)
    assert result.quality_score == 90.0
