"""Tests for base module — ProjectRule ABC and scoring constants."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.models.results import CheckResult


class TestProjectRule:
    """Tests for ProjectRule ABC."""

    def test_is_abstract(self) -> None:
        """ProjectRule cannot be instantiated directly."""
        from axm_audit.core.rules.base import ProjectRule

        with pytest.raises(TypeError):
            ProjectRule()  # type: ignore[abstract]

    def test_has_rule_id_property(self) -> None:
        """ProjectRule declares abstract rule_id property."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "rule_id")

    def test_has_category_property(self) -> None:
        """ProjectRule declares abstract category property."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "category")
        # Verify it's abstract — included in __abstractmethods__
        assert "category" in ProjectRule.__abstractmethods__

    def test_has_check_method(self) -> None:
        """ProjectRule declares abstract check method."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "check")

    def test_check_src_returns_none_when_exists(self, tmp_path: Path) -> None:
        """check_src returns None when src/ exists (rule should continue)."""
        from axm_audit.core.rules.base import ProjectRule

        (tmp_path / "src").mkdir()

        class _ConcreteRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "TEST_RULE"

            @property
            def category(self) -> str:
                return "testing"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        rule = _ConcreteRule()
        assert rule.check_src(tmp_path) is None

    def test_check_src_returns_result_when_missing(self, tmp_path: Path) -> None:
        """check_src returns a passing CheckResult when src/ is missing."""
        from axm_audit.core.rules.base import ProjectRule

        class _ConcreteRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "TEST_RULE"

            @property
            def category(self) -> str:
                return "testing"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        rule = _ConcreteRule()
        result = rule.check_src(tmp_path)
        assert result is not None
        assert result.passed is True
        assert result.rule_id == "TEST_RULE"
        assert result.details == {"score": 100}
        assert "src/ directory not found" in result.message


class TestScoringConstants:
    """Tests for shared scoring constants."""

    def test_pass_threshold_value(self) -> None:
        """PASS_THRESHOLD should be 90."""
        from axm_audit.core.rules.base import PASS_THRESHOLD

        assert PASS_THRESHOLD == 90

    def test_complexity_threshold_value(self) -> None:
        """COMPLEXITY_THRESHOLD should be 10."""
        from axm_audit.core.rules.base import COMPLEXITY_THRESHOLD

        assert COMPLEXITY_THRESHOLD == 10

    def test_perfect_score_value(self) -> None:
        """PERFECT_SCORE should be 100."""
        from axm_audit.core.rules.base import PERFECT_SCORE

        assert PERFECT_SCORE == 100
