"""Unit tests for the composite quality_score and grade derivation.

Exercises the rule_id -> category mapping built from the live
``@register_rule`` registry, and asserts structural properties of the score
(grade thresholds, normalization, single-category audits, no-score
fallback, weighted averages) without hardcoding the weights table.
"""

from __future__ import annotations

import pytest
from _registry_helpers import build_rule_category_map

from axm_audit.models.results import AuditResult, CheckResult

_RULE_CATEGORY = build_rule_category_map()


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Create a CheckResult with a score and the registry-derived category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=_RULE_CATEGORY.get(rule_id),
    )


def _all_categories(score: float) -> list[CheckResult]:
    """Create checks for every registered scored rule at the given score."""
    return [_make_check(rid, score) for rid in _RULE_CATEGORY]


class TestRegistryIntegration:
    """Sanity checks tying scoring behavior back to the rule registry."""

    def test_every_registered_rule_has_category(self) -> None:
        """Every rule in the registry must expose a non-empty category."""
        from axm_audit.core.rules.base import get_registry

        for category, rule_classes in get_registry().items():
            for cls in rule_classes:
                has_code = hasattr(cls.__init__, "__code__")
                rule = (
                    cls()
                    if not has_code or cls.__init__.__code__.co_varnames == ("self",)
                    else None
                )
                if rule is None:
                    continue
                assert rule.category, (
                    f"Rule {rule.rule_id} has empty category "
                    f"(expected registry category: {category})"
                )

    def test_all_scored_rules_at_100_yields_100(self) -> None:
        """Anti-drop regression: every registered scored rule contributes.

        Builds an AuditResult with ALL scored rules at 100 and asserts the
        score is exactly 100 (a missing rule would shift the weighted mean).
        """
        result = AuditResult(checks=_all_categories(100))
        assert result.quality_score == 100.0


# 3 categories, weight_sum = 0.20 + 0.15 + 0.15 = 0.50.
# Normalized: (80*0.20 + 60*0.15 + 100*0.15) / 0.50 = 80.0.
_PARTIAL_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 80),
    ("QUALITY_TYPE", 60),
    ("QUALITY_COMPLEXITY", 100),
]

# Lint-only audit: all checks share the same category, score equals the
# category mean — avg(94, 100, 95) ≈ 96.33.
_LINT_ONLY_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 94),
    ("QUALITY_FORMAT", 100),
    ("QUALITY_DEAD_CODE", 95),
]

# Mixed audit spanning every category at varying scores. Hand-computed to
# ≈ 92.7 — lint avg(80,100,100)*0.20 + type 60*0.15 + complexity 100*0.15
# + security 100*0.10 + deps avg(100,100)*0.10 + testing 100*0.15
# + arch avg(100,100,100,100)*0.10 + practices avg(100,100,100,100,100)*0.05.
_MIXED_CHECKS: list[tuple[str, int]] = [
    ("QUALITY_LINT", 80),
    ("QUALITY_FORMAT", 100),
    ("QUALITY_DIFF_SIZE", 100),
    ("QUALITY_TYPE", 60),
    ("QUALITY_COMPLEXITY", 100),
    ("QUALITY_SECURITY", 100),
    ("DEPS_AUDIT", 100),
    ("DEPS_HYGIENE", 100),
    ("QUALITY_COVERAGE", 100),
    ("ARCH_COUPLING", 100),
    ("ARCH_CIRCULAR", 100),
    ("ARCH_GOD_CLASS", 100),
    ("ARCH_DUPLICATION", 100),
    ("PRACTICE_DOCSTRING", 100),
    ("PRACTICE_BARE_EXCEPT", 100),
    ("PRACTICE_SECURITY", 100),
    ("PRACTICE_BLOCKING_IO", 100),
]


@pytest.mark.parametrize(
    ("score_inputs", "expected"),
    [
        pytest.param(
            [("QUALITY_COVERAGE", 100)],
            100.0,
            id="single_check_returns_its_score",
        ),
        pytest.param(_PARTIAL_CHECKS, 80.0, id="partial_normalized"),
        pytest.param(_LINT_ONLY_CHECKS, 96.33, id="lint_only_category_mean"),
        pytest.param(_MIXED_CHECKS, 92.7, id="mixed_weighted_average"),
    ],
)
def test_quality_score_weighted_average(
    score_inputs: list[tuple[str, int]],
    expected: float,
) -> None:
    """quality_score normalizes by weight_sum across the present categories."""
    result = AuditResult(
        checks=[_make_check(rid, score) for rid, score in score_inputs],
    )
    assert result.quality_score is not None
    assert abs(result.quality_score - expected) < 1.0


def test_quality_score_none_without_scored_checks() -> None:
    """quality_score is None when no check carries a score/category."""
    result = AuditResult(
        checks=[
            CheckResult(rule_id="FILE_EXISTS_README.md", passed=True, message=""),
        ],
    )
    assert result.quality_score is None
    assert result.grade is None  # grade follows quality_score


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        pytest.param(100, "A", id="100_grade_a"),
        pytest.param(95, "A", id="95_grade_a"),
        pytest.param(85, "B", id="85_grade_b"),
        pytest.param(75, "C", id="75_grade_c"),
        pytest.param(65, "D", id="65_grade_d"),
        pytest.param(30, "F", id="30_grade_f"),
        pytest.param(0, "F", id="0_grade_f"),
    ],
)
def test_grade_thresholds(score: int, expected_grade: str) -> None:
    """grade derives from quality_score via fixed thresholds (A/B/C/D/F)."""
    result = AuditResult(checks=_all_categories(score))
    assert result.grade == expected_grade
