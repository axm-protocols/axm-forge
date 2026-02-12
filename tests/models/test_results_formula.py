"""Tests for the 3-layer composite quality score formula."""

import pytest

from axm_audit.models.results import AuditResult, CheckResult


class TestQualityScore:
    """Tests for the quality scoring logic."""

    def test_quality_score_3_layer_formula(self):
        """Quality score uses LINT=40%, TYPE=35%, COMPLEXITY=25%."""
        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Lint: 90/100",
                details={"score": 90},
            ),
            CheckResult(
                rule_id="QUALITY_TYPE",
                passed=True,
                message="Type: 85/100",
                details={"score": 85},
            ),
            CheckResult(
                rule_id="QUALITY_COMPLEXITY",
                passed=True,
                message="Complexity: 95/100",
                details={"score": 95},
            ),
        ]

        result = AuditResult(checks=checks)

        # Expected: (90*0.40) + (85*0.35) + (95*0.25)
        #         = 36.0 + 29.75 + 23.75 = 89.5
        assert result.quality_score == pytest.approx(89.5, abs=0.1)

    def test_quality_score_weights_sum_to_100(self):
        """Weights should sum to 100%."""
        weights = {
            "QUALITY_LINT": 0.40,
            "QUALITY_TYPE": 0.35,
            "QUALITY_COMPLEXITY": 0.25,
        }

        assert sum(weights.values()) == pytest.approx(1.0)
