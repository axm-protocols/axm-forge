"""Tests for auditor integration of security rules."""

from axm_audit.core.auditor import get_rules_for_category


def test_security_rule_in_practice_category():
    """SecurityPatternRule should be in the practice category."""
    rules = get_rules_for_category("practice")
    rule_types = [type(r).__name__ for r in rules]
    assert "SecurityPatternRule" in rule_types
