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
        """category is concrete, auto-injected by @register_rule."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "category")
        # category is no longer abstract — it reads from _registered_category
        assert "category" not in ProjectRule.__abstractmethods__

    def test_has_check_method(self) -> None:
        """ProjectRule declares abstract check method."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "check")

    def test_check_src_returns_none_when_exists(self, tmp_path: Path) -> None:
        """check_src returns None when src/ exists (rule should continue)."""
        from axm_audit.core.rules.base import ProjectRule

        (tmp_path / "src").mkdir()

        class _ConcreteRule(ProjectRule):
            _registered_category = "testing"

            @property
            def rule_id(self) -> str:
                return "TEST_RULE"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        rule = _ConcreteRule()
        assert rule.check_src(tmp_path) is None

    def test_check_src_returns_result_when_missing(self, tmp_path: Path) -> None:
        """check_src returns a passing CheckResult when src/ is missing."""
        from axm_audit.core.rules.base import ProjectRule

        class _ConcreteRule(ProjectRule):
            _registered_category = "testing"

            @property
            def rule_id(self) -> str:
                return "TEST_RULE"

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


class TestRegisterRule:
    """Tests for @register_rule decorator."""

    def test_register_rule_populates_registry(self) -> None:
        """Decorated class appears in the registry."""
        from axm_audit.core.rules.base import _RULE_REGISTRY, ProjectRule, register_rule

        @register_rule("_test_cat")
        class _DummyRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "DUMMY"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        assert _DummyRule in _RULE_REGISTRY["_test_cat"]
        # Cleanup
        _RULE_REGISTRY["_test_cat"].remove(_DummyRule)
        if not _RULE_REGISTRY["_test_cat"]:
            del _RULE_REGISTRY["_test_cat"]

    def test_registry_deduplication(self) -> None:
        """Registering the same class twice doesn't duplicate it."""
        from axm_audit.core.rules.base import _RULE_REGISTRY, ProjectRule, register_rule

        @register_rule("_test_dedup")
        class _DedupeRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "DEDUPE"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        # Register again manually
        register_rule("_test_dedup")(_DedupeRule)

        assert _RULE_REGISTRY["_test_dedup"].count(_DedupeRule) == 1
        # Cleanup
        _RULE_REGISTRY["_test_dedup"].remove(_DedupeRule)
        if not _RULE_REGISTRY["_test_dedup"]:
            del _RULE_REGISTRY["_test_dedup"]


class TestGetRegistry:
    """Tests for get_registry()."""

    def test_registry_has_all_categories(self) -> None:
        """Registry contains all expected auditor categories after import."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit.core.rules.base import get_registry

        reg = get_registry()
        expected = {
            "lint",
            "type",
            "complexity",
            "architecture",
            "practices",
            "security",
            "deps",
            "testing",
            "structure",
            "tooling",
            "test_quality",
        }
        assert expected == set(reg.keys())

    def test_registry_total_rule_count(self) -> None:
        """Registry contains 25 total rule classes."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit.core.rules.base import get_registry

        reg = get_registry()
        total = sum(len(v) for v in reg.values())
        assert total == 25
