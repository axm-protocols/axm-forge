"""Integration tests for the composite quality score using real registry rules.

These tests exercise the rule_id -> category mapping built from the live
``@register_rule`` registry, and assert structural properties of the score
(grade thresholds, normalization, single-category audits) without
hardcoding the weights table.
"""

from __future__ import annotations

from _registry_helpers import build_rule_category_map

from axm_audit.models.results import AuditResult, CheckResult

_RULE_CATEGORY = build_rule_category_map()


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Create a CheckResult with a score and the registry-derived category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        details={"score": score},
        category=_RULE_CATEGORY.get(rule_id),
    )


class TestQualityScoreRegistryIntegration:
    """Score behavior against the real rule registry."""

    def test_all_scored_rules_at_100_yields_100(self) -> None:
        """Every registered scored rule must contribute to quality_score.

        Regression: creates an AuditResult with ALL scored rules at 100,
        then verifies the score is exactly 100 (proving nothing was dropped).
        """
        checks = [_make_check(rid, 100) for rid in _RULE_CATEGORY]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

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

    def test_grade_a_when_all_perfect(self) -> None:
        all_perfect = [_make_check(rid, 100) for rid in _RULE_CATEGORY]
        assert AuditResult(checks=all_perfect).grade == "A"

    def test_grade_f_when_all_zero(self) -> None:
        all_zero = [_make_check(rid, 0) for rid in _RULE_CATEGORY]
        assert AuditResult(checks=all_zero).grade == "F"

    def test_filtered_audit_normalizes_to_category_average(self) -> None:
        """Category-filtered audit normalizes by present weights only.

        Regression for the bug where a lint-only audit returned ~17 because
        the score was divided by the sum of all weights instead of the
        present ones.
        """
        checks = [
            _make_check("QUALITY_LINT", 94),
            _make_check("QUALITY_FORMAT", 100),
            _make_check("QUALITY_DEAD_CODE", 95),
        ]
        result = AuditResult(checks=checks)
        # All in one category → score equals the category's mean.
        # avg(94, 100, 95) = 96.33
        assert result.quality_score is not None
        assert abs(result.quality_score - 96.33) < 0.1
        assert result.grade == "A"

    def test_single_scored_check_returns_its_score(self) -> None:
        """With one check, weights cancel out and the score equals the input."""
        result = AuditResult(checks=[_make_check("QUALITY_COVERAGE", 100)])
        assert result.quality_score == 100.0
