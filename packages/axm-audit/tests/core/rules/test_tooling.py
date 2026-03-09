"""Tests for ToolAvailabilityRule — RED phase."""

from pathlib import Path


class TestToolAvailabilityRule:
    """Tests for tool availability checks."""

    def test_tool_found_python(self) -> None:
        """Python should always be available."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule

        rule = ToolAvailabilityRule(tool_name="python3")
        result = rule.check(Path("."))
        assert result.passed is True
        assert "found" in result.message

    def test_tool_not_found(self) -> None:
        """Non-existent tool should fail."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule

        rule = ToolAvailabilityRule(tool_name="nonexistent_tool_xyz_12345")
        result = rule.check(Path("."))
        assert result.passed is False
        assert result.fix_hint is not None

    def test_rule_id_format(self) -> None:
        """Rule ID should be TOOL_<NAME> uppercase."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule

        rule = ToolAvailabilityRule(tool_name="ruff")
        assert rule.rule_id == "TOOL_RUFF"

    def test_non_critical_missing_tool_has_warning_severity(self) -> None:
        """Non-critical missing tool should have WARNING severity."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule
        from axm_audit.models.results import Severity

        rule = ToolAvailabilityRule(tool_name="nonexistent_xyz", critical=False)
        result = rule.check(Path("."))
        assert result.passed is False
        assert result.severity == Severity.WARNING

    def test_critical_missing_tool_has_error_severity(self) -> None:
        """Critical missing tool should have ERROR severity."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule
        from axm_audit.models.results import Severity

        rule = ToolAvailabilityRule(tool_name="nonexistent_xyz", critical=True)
        result = rule.check(Path("."))
        assert result.passed is False
        assert result.severity == Severity.ERROR

    def test_found_tool_has_info_severity(self) -> None:
        """Found tool should have INFO severity."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule
        from axm_audit.models.results import Severity

        rule = ToolAvailabilityRule(tool_name="python3")
        result = rule.check(Path("."))
        assert result.severity == Severity.INFO
