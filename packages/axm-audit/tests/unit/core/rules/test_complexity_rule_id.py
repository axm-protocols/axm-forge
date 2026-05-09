"""Unit test for ComplexityRule rule_id (no I/O)."""

from __future__ import annotations


class TestComplexityRuleUnit:
    """Pure unit tests for ComplexityRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_COMPLEXITY."""
        from axm_audit.core.rules.complexity import ComplexityRule

        rule = ComplexityRule()
        assert rule.rule_id == "QUALITY_COMPLEXITY"
