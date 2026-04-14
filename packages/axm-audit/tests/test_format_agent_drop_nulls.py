"""Tests for format_agent null-field dropping (AXM-1410)."""

from __future__ import annotations

import json


class TestFormatAgentFailedNoNullKeys:
    """Unit: failed check dicts omit None-valued keys."""

    def test_format_agent_failed_no_null_keys(self) -> None:
        """Failed check with all None optional fields has only rule_id+message."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=False,
                    message="Lint failed",
                    text=None,
                    details=None,
                    fix_hint=None,
                ),
            ]
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert set(failed.keys()) == {"rule_id", "message"}


class TestFormatAgentFailedPreservesValues:
    """Unit: failed check dicts preserve all non-None values."""

    def test_format_agent_failed_preserves_values(self) -> None:
        """Failed check with all fields populated keeps all 5 keys."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=False,
                    message="Lint failed",
                    text="x",
                    details={"a": 1},
                    fix_hint="do Y",
                ),
            ]
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert failed["rule_id"] == "QUALITY_LINT"
        assert failed["message"] == "Lint failed"
        assert failed["text"] == "x"
        assert failed["details"] == {"a": 1}
        assert failed["fix_hint"] == "do Y"
        assert len(failed) == 5


class TestFormatAgentPassedActionableNoNullKeys:
    """Unit: passed actionable check dicts omit None-valued keys."""

    def test_format_agent_passed_actionable_no_null_keys(self) -> None:
        """Passed check with actionable details but no fix_hint."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_DOCS",
                    passed=True,
                    message="Missing docstrings",
                    details={"missing": ["foo", "bar"]},
                    fix_hint=None,
                ),
            ]
        )
        output = format_agent(result)
        passed_entry = output["passed"][0]
        assert isinstance(passed_entry, dict)
        assert "fix_hint" not in passed_entry
        assert passed_entry["rule_id"] == "QUALITY_DOCS"
        assert passed_entry["message"] == "Missing docstrings"
        assert passed_entry["details"] == {"missing": ["foo", "bar"]}


class TestFormatAgentTokenSavings:
    """Functional: null-dropping reduces serialized output size."""

    def test_format_agent_token_savings(self) -> None:
        """AuditResult with 3 minimal failures serializes smaller than pre-refactor."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        checks = [
            CheckResult(
                rule_id=f"RULE_{i}",
                passed=False,
                message=f"Failed {i}",
                text=None,
                details=None,
                fix_hint=None,
            )
            for i in range(3)
        ]
        result = AuditResult(checks=checks)
        output = format_agent(result)
        serialized = json.dumps(output)

        # Pre-refactor equivalent: each failed dict would have all 5 keys
        pre_refactor_failed = [
            {
                "rule_id": f"RULE_{i}",
                "message": f"Failed {i}",
                "text": None,
                "details": None,
                "fix_hint": None,
            }
            for i in range(3)
        ]
        pre_refactor = {
            "score": output["score"],
            "grade": output["grade"],
            "passed": output["passed"],
            "failed": pre_refactor_failed,
        }
        pre_refactor_serialized = json.dumps(pre_refactor)

        assert len(serialized) < len(pre_refactor_serialized)


class TestFormatAgentEdgeCases:
    """Edge cases for null-dropping behavior."""

    def test_all_fields_populated(self) -> None:
        """Failed check with all 5 fields non-null keeps all keys."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="R1",
                    passed=False,
                    message="msg",
                    text="t",
                    details={"x": 1},
                    fix_hint="fix",
                ),
            ]
        )
        output = format_agent(result)
        assert len(output["failed"][0]) == 5

    def test_only_message_and_rule_id(self) -> None:
        """Minimal failure has exactly 2 keys."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="STRUCT_1",
                    passed=False,
                    message="structure issue",
                    text=None,
                    details=None,
                    fix_hint=None,
                ),
            ]
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert set(failed.keys()) == {"rule_id", "message"}

    def test_empty_string_vs_none(self) -> None:
        """Empty string is not None — text key is preserved."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="R1",
                    passed=False,
                    message="msg",
                    text="",
                    details=None,
                    fix_hint=None,
                ),
            ]
        )
        output = format_agent(result)
        failed = output["failed"][0]
        assert "text" in failed
        assert failed["text"] == ""
