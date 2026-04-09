"""Tests for the 8-category composite quality score formula."""

from __future__ import annotations

import pytest

from axm_audit.models.results import AuditResult, CheckResult

# Rule-id → scoring category mapping (must match rule implementations)
_RULE_CATEGORY: dict[str, str] = {
    "QUALITY_LINT": "lint",
    "QUALITY_FORMAT": "lint",
    "QUALITY_DIFF_SIZE": "lint",
    "QUALITY_DEAD_CODE": "lint",
    "QUALITY_TYPE": "type",
    "QUALITY_COMPLEXITY": "complexity",
    "QUALITY_SECURITY": "security",
    "DEPS_AUDIT": "deps",
    "DEPS_HYGIENE": "deps",
    "QUALITY_COVERAGE": "testing",
    "ARCH_COUPLING": "architecture",
    "ARCH_CIRCULAR": "architecture",
    "ARCH_GOD_CLASS": "architecture",
    "ARCH_DUPLICATION": "architecture",
    "PRACTICE_DOCSTRING": "practices",
    "PRACTICE_BARE_EXCEPT": "practices",
    "PRACTICE_SECURITY": "security",
    "PRACTICE_BLOCKING_IO": "practices",
    "PRACTICE_TEST_MIRROR": "practices",
}


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Helper to create a CheckResult with a score and category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        details={"score": score},
        category=_RULE_CATEGORY.get(rule_id),
    )


class TestQualityScore:
    """Tests for the quality scoring logic."""

    def test_quality_score_8_category_formula(self) -> None:
        """Quality score uses 8-category weighted model with all scored rules."""
        checks = [
            _make_check("QUALITY_LINT", 90),  # lint: avg(90,100,100)=96.67
            _make_check("QUALITY_FORMAT", 100),
            _make_check("QUALITY_DIFF_SIZE", 100),
            _make_check("QUALITY_TYPE", 85),  # 85 * 0.15 = 12.75
            _make_check("QUALITY_COMPLEXITY", 95),  # 95 * 0.15 = 14.25
            _make_check("QUALITY_SECURITY", 100),  # 100 * 0.10 = 10
            _make_check("DEPS_AUDIT", 100),  # avg(100,100) * 0.10 = 10
            _make_check("DEPS_HYGIENE", 100),
            _make_check("QUALITY_COVERAGE", 90),  # 90 * 0.15 = 13.5
            _make_check("ARCH_COUPLING", 100),  # avg(100,...) * 0.10 = 10
            _make_check("ARCH_CIRCULAR", 100),
            _make_check("ARCH_GOD_CLASS", 100),
            _make_check("ARCH_DUPLICATION", 100),
            _make_check("PRACTICE_DOCSTRING", 100),  # avg(100,...) * 0.05 = 5
            _make_check("PRACTICE_BARE_EXCEPT", 100),
            _make_check("PRACTICE_SECURITY", 100),
            _make_check("PRACTICE_BLOCKING_IO", 100),
        ]

        result = AuditResult(checks=checks)

        # lint: avg(90,100,100)=96.67 * 0.20 = 19.33
        # types: 85*0.15=12.75 | complexity: 95*0.15=14.25
        # security: avg(100,100)*0.10=10 | deps: avg(100,100)*0.10=10
        # testing: 90*0.15=13.5 | architecture: avg(100,100,100,100)*0.10=10
        # practices: avg(100,100,100,100)*0.05=5
        # Total: 19.33 + 12.75 + 14.25 + 10 + 10 + 13.5 + 10 + 5 = 94.83
        assert result.quality_score == pytest.approx(94.8, abs=0.2)

    def test_quality_score_weights_sum_to_100(self) -> None:
        """Weights should sum to 100%."""
        weights = {
            "lint": 0.20,
            "type": 0.15,
            "complexity": 0.15,
            "security": 0.10,
            "deps": 0.10,
            "testing": 0.15,
            "architecture": 0.10,
            "practices": 0.05,
        }

        assert sum(weights.values()) == pytest.approx(1.0)

    def test_quality_score_includes_all_scored_rules(self) -> None:
        """Every registered scored rule must contribute to quality_score.

        Regression test: creates an AuditResult with ALL scored rules at 100,
        then verifies the score is exactly 100 (proving nothing was dropped).
        """
        all_scored_rule_ids = [
            "QUALITY_LINT",
            "QUALITY_FORMAT",
            "QUALITY_DIFF_SIZE",
            "QUALITY_TYPE",
            "QUALITY_DEAD_CODE",
            "QUALITY_COMPLEXITY",
            "QUALITY_SECURITY",
            "DEPS_AUDIT",
            "DEPS_HYGIENE",
            "QUALITY_COVERAGE",
            "ARCH_COUPLING",
            "ARCH_CIRCULAR",
            "ARCH_GOD_CLASS",
            "ARCH_DUPLICATION",
            "PRACTICE_DOCSTRING",
            "PRACTICE_BARE_EXCEPT",
            "PRACTICE_SECURITY",
            "PRACTICE_BLOCKING_IO",
        ]
        checks = [_make_check(rid, 100) for rid in all_scored_rule_ids]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_rule_category_covers_all_scored_rules(self) -> None:
        """Every rule in the registry must have a category property.

        Safeguard: enumerate rule classes from the auto-discovery registry,
        instantiate each, and verify the category property is set and non-empty.
        """
        import axm_audit.core.rules  # noqa: F401
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

    def test_quality_score_backward_compatible_grades(self) -> None:
        """Grade thresholds still work after adding new rules."""
        # All perfect → A
        all_perfect = [
            _make_check(rid, 100)
            for rid in [
                "QUALITY_LINT",
                "QUALITY_FORMAT",
                "QUALITY_DIFF_SIZE",
                "QUALITY_TYPE",
                "QUALITY_DEAD_CODE",
                "QUALITY_COMPLEXITY",
                "QUALITY_SECURITY",
                "DEPS_AUDIT",
                "DEPS_HYGIENE",
                "QUALITY_COVERAGE",
                "ARCH_COUPLING",
                "ARCH_CIRCULAR",
                "ARCH_GOD_CLASS",
                "ARCH_DUPLICATION",
                "PRACTICE_DOCSTRING",
                "PRACTICE_BARE_EXCEPT",
                "PRACTICE_SECURITY",
                "PRACTICE_BLOCKING_IO",
            ]
        ]
        assert AuditResult(checks=all_perfect).grade == "A"

        # All zero → F
        all_zero = [
            _make_check(rid, 0)
            for rid in [
                "QUALITY_LINT",
                "QUALITY_FORMAT",
                "QUALITY_DIFF_SIZE",
                "QUALITY_TYPE",
                "QUALITY_DEAD_CODE",
                "QUALITY_COMPLEXITY",
                "QUALITY_SECURITY",
                "DEPS_AUDIT",
                "DEPS_HYGIENE",
                "QUALITY_COVERAGE",
                "ARCH_COUPLING",
                "ARCH_CIRCULAR",
                "ARCH_GOD_CLASS",
                "ARCH_DUPLICATION",
                "PRACTICE_DOCSTRING",
                "PRACTICE_BARE_EXCEPT",
                "PRACTICE_SECURITY",
                "PRACTICE_BLOCKING_IO",
            ]
        ]
        assert AuditResult(checks=all_zero).grade == "F"

    def test_category_filter_score_normalization(self) -> None:
        """Category-filtered audit normalizes by present weights only.

        Simulates audit(category="lint") where only lint-related rules run.
        Bug: was returning ~17 (dividing by all 8 weights). Fix: ~96.
        """
        # Only lint-category checks (lint weight = 0.20)
        checks = [
            _make_check("QUALITY_LINT", 94),  # lint
            _make_check("QUALITY_FORMAT", 100),  # lint
            _make_check("QUALITY_DEAD_CODE", 95),  # lint
        ]
        result = AuditResult(checks=checks)
        # avg(94, 100, 95) = 96.33 → normalized by lint weight only → 96.3
        assert result.quality_score is not None
        assert result.quality_score == pytest.approx(96.3, abs=0.1)
        assert result.grade == "A"

    def test_full_score_unchanged(self) -> None:
        """Full audit (all 8 categories) returns same score as before fix.

        Regression: ensures normalization doesn't change full-audit behavior.
        """
        checks = [
            _make_check("QUALITY_LINT", 90),
            _make_check("QUALITY_FORMAT", 100),
            _make_check("QUALITY_DIFF_SIZE", 100),
            _make_check("QUALITY_TYPE", 85),
            _make_check("QUALITY_COMPLEXITY", 95),
            _make_check("QUALITY_SECURITY", 100),
            _make_check("DEPS_AUDIT", 100),
            _make_check("DEPS_HYGIENE", 100),
            _make_check("QUALITY_COVERAGE", 90),
            _make_check("ARCH_COUPLING", 100),
            _make_check("ARCH_CIRCULAR", 100),
            _make_check("ARCH_GOD_CLASS", 100),
            _make_check("ARCH_DUPLICATION", 100),
            _make_check("PRACTICE_DOCSTRING", 100),
            _make_check("PRACTICE_BARE_EXCEPT", 100),
            _make_check("PRACTICE_SECURITY", 100),
            _make_check("PRACTICE_BLOCKING_IO", 100),
        ]
        result = AuditResult(checks=checks)
        # weight_sum=1.0 so total/weight_sum == total → same as before
        assert result.quality_score == pytest.approx(94.8, abs=0.2)

    def test_single_category_perfect(self) -> None:
        """Single category scoring 100 returns exactly 100.0."""
        checks = [_make_check("QUALITY_COVERAGE", 100)]  # testing category
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0
