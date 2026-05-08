"""Tests for audit models."""

import pytest
from _registry_helpers import (
    SCORED_CATEGORIES,
    build_rule_category_map,
    scored_rule_ids,
)

from axm_audit.models.results import AuditResult, CheckResult


class TestCheckResult:
    """Tests for CheckResult model."""

    def test_passed_check(self) -> None:
        """Passed check should have passed=True."""
        from axm_audit.models.results import CheckResult

        result = CheckResult(
            rule_id="FILE_EXISTS",
            passed=True,
            message="pyproject.toml exists",
        )
        assert result.passed is True
        assert result.rule_id == "FILE_EXISTS"

    def test_failed_check(self) -> None:
        """Failed check should have passed=False."""
        from axm_audit.models.results import CheckResult

        result = CheckResult(
            rule_id="FILE_EXISTS",
            passed=False,
            message="README.md not found",
        )
        assert result.passed is False

    def test_audit_result_creation(self):
        """Test creating an AuditResult instance."""
        from axm_audit.models import AuditResult, CheckResult

        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])

        assert result.total == 1
        assert result.success is True

    def test_audit_result_failure(self) -> None:
        """Audit with some checks failed."""
        from axm_audit.models.results import AuditResult, CheckResult

        checks = [
            CheckResult(rule_id="F1", passed=True, message="OK"),
            CheckResult(rule_id="F2", passed=False, message="FAIL"),
        ]
        result = AuditResult(checks=checks)
        assert result.success is False
        assert result.total == 2
        assert result.failed == 1

    def test_json_serialization(self) -> None:
        """AuditResult should serialize to valid JSON for Agents."""
        import json

        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[CheckResult(rule_id="TEST", passed=True, message="OK")]
        )
        data = json.loads(result.model_dump_json())
        assert "checks" in data
        assert "success" in data
        assert data["success"] is True

    def test_audit_result_quality_score(self):
        """Test that quality scoring works."""
        from axm_audit.models import AuditResult, CheckResult

        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                score=90,
                category="lint",
            ),
            CheckResult(
                rule_id="QUALITY_TYPE",
                passed=False,
                message="Fail",
                score=50,
                category="type",
            ),
        ]
        result = AuditResult(checks=checks)

        assert result.quality_score is not None
        assert 0 <= result.quality_score <= 100

    def test_audit_result_grade(self):
        """Test that letter grading works."""
        from axm_audit.models import AuditResult, CheckResult

        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                score=95,
                category="lint",
            )
        ]
        result = AuditResult(checks=checks)

        assert result.grade in ["A", "B", "C", "D", "F"]


class TestRegistryDerivedScoring:
    """Scoring tests that derive rule lists from get_registry()."""

    def test_all_perfect_scores_100(self) -> None:
        """All scored rules at 100 via registry -> quality_score == 100.0."""
        category_map = build_rule_category_map()
        checks = [_make_check(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_all_zero_scores_grade_f(self) -> None:
        """All scored rules at 0 via registry -> grade == 'F'."""
        category_map = build_rule_category_map()
        checks = [_make_check(rid, 0, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == pytest.approx(0.0, abs=0.1)
        assert result.grade == "F"

    def test_registry_covers_all_scored_categories(self) -> None:
        """Registry must provide at least one rule per scored category."""
        category_map = build_rule_category_map()
        covered = set(category_map.values())
        missing = SCORED_CATEGORIES - covered
        assert not missing, f"Scored categories missing from registry: {missing}"

    def test_rule_addition_no_test_change(self) -> None:
        """Adding a rule to the registry doesn't break scoring tests.

        This is structural: the test itself proves resilience because
        it derives everything from the registry. If a new rule is added,
        it will be automatically included in the checks list.
        """
        category_map = build_rule_category_map()
        assert len(category_map) > 0, "Registry should have at least one scored rule"
        checks = [_make_check(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_scored_rule_ids_non_empty(self) -> None:
        """scored_rule_ids must return a non-empty list."""
        ids = scored_rule_ids()
        assert len(ids) > 0
        # Each ID should be a non-empty string
        for rid in ids:
            assert isinstance(rid, str)
            assert len(rid) > 0


def _make_check(
    rule_id: str, score: float, category_map: dict[str, str]
) -> CheckResult:
    """Create a CheckResult with score and category from the registry map."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=category_map.get(rule_id),
    )
