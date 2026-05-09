"""Integration tests for ProjectRule.check_src against a real filesystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.models.results import CheckResult

pytestmark = pytest.mark.integration


class TestProjectRuleSrcCheck:
    """Tests for ProjectRule.check_src against a real filesystem."""

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
        assert result.score == 100
        assert result.details is None
        assert "src/ directory not found" in result.message
