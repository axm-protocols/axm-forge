"""Integration: score/grade serialization over real ``AuditResult`` graphs.

Exercises the collaboration between ``collect_category_scores`` (category
grouping + N/A drop), ``AuditResult.quality_score`` (weight-normalisation) and
``resolve_score_grade`` (the single serialization surface), rather than any one
in isolation — the project level and category level must agree on N/A.
"""

from __future__ import annotations

import pytest

from axm_audit.models.results import AuditResult, CheckResult, collect_category_scores
from axm_audit.score import (
    ScoreIncalculableError,
    resolve_score_grade,
    score_grade_or_none,
)

pytestmark = pytest.mark.integration


def _check(rule_id: str, category: str, score: int | None) -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=score is None or score >= 60,
        message="synthetic",
        category=category,
        score=score,
    )


def test_all_not_applicable_category_set_surfaces_na_end_to_end() -> None:
    """AC2: an audit whose scored categories are every one not-applicable
    resolves to N/A at the project level — never 0.0/``"F"``."""
    checks = [
        _check("QUALITY_LINT", "lint", None),
        _check("QUALITY_TYPE", "type", None),
        _check("QUALITY_SECURITY", "security", None),
    ]
    # The grouping layer drops every not-applicable score -> nothing to average.
    assert collect_category_scores(checks) == {}

    result = AuditResult(checks=checks)
    assert result.quality_score is None
    assert result.grade is None

    assert score_grade_or_none(result) == (None, None)
    with pytest.raises(ScoreIncalculableError):
        resolve_score_grade(result)


def test_mixed_set_matches_absent_category_set() -> None:
    """AC1: a set mixing measured + not-applicable categories resolves to the
    exact same (score, grade) as the same set with the N/A category removed."""
    measured = [
        _check("QUALITY_LINT", "lint", 80),
        _check("QUALITY_TYPE", "type", 100),
    ]
    na = _check("QUALITY_SECURITY", "security", None)

    mixed = AuditResult(checks=[*measured, na])
    without_na = AuditResult(checks=list(measured))

    # The N/A category is dropped by the grouping layer, so both graphs group
    # to the identical measured-only category map ...
    assert collect_category_scores(mixed.checks) == collect_category_scores(
        without_na.checks
    )
    # ... and therefore serialize to the identical (score, grade).
    assert resolve_score_grade(mixed) == resolve_score_grade(without_na)
    assert mixed.quality_score == without_na.quality_score
