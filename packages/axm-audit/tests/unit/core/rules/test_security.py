"""Unit-scope tests for SecurityRule."""

from __future__ import annotations

from axm_audit.core.rules.security import SecurityRule


class TestUnitScope:
    """Unit-scope tests for SecurityRule."""

    def test_rule_id(self) -> None:
        """Rule ID should be QUALITY_SECURITY."""
        rule = SecurityRule()
        assert rule.rule_id == "QUALITY_SECURITY"
