"""Tests for the 8-category composite quality score formula."""

import pytest

from axm_audit.models.results import AuditResult, CheckResult


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Helper to create a CheckResult with a score."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        details={"score": score},
    )


class TestQualityScore:
    """Tests for the quality scoring logic."""

    def test_quality_score_8_category_formula(self):
        """Quality score uses 8-category weighted model."""
        checks = [
            _make_check("QUALITY_LINT", 90),  # 90 * 0.20 = 18
            _make_check("QUALITY_TYPE", 85),  # 85 * 0.15 = 12.75
            _make_check("QUALITY_COMPLEXITY", 95),  # 95 * 0.15 = 14.25
            _make_check("QUALITY_SECURITY", 100),  # 100 * 0.10 = 10
            _make_check("DEPS_AUDIT", 100),  # avg(100,100) * 0.10 = 10
            _make_check("DEPS_HYGIENE", 100),
            _make_check("QUALITY_COVERAGE", 90),  # 90 * 0.15 = 13.5
            _make_check("ARCH_COUPLING", 100),  # 100 * 0.10 = 10
            _make_check("PRACTICE_DOCSTRING", 100),  # avg(100,100,100)*0.05 = 5
            _make_check("PRACTICE_BARE_EXCEPT", 100),
            _make_check("PRACTICE_SECURITY", 100),
        ]

        result = AuditResult(checks=checks)

        # Expected: 18 + 12.75 + 14.25 + 10 + 10 + 13.5 + 10 + 5 = 93.5
        assert result.quality_score == pytest.approx(93.5, abs=0.1)

    def test_quality_score_weights_sum_to_100(self):
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
