"""Unit tests for BareExceptRule (pure)."""

from __future__ import annotations

from axm_audit.core.rules.practices.bare_except import BareExceptRule


class TestBareExceptRuleUnit:
    """Tests for BareExceptRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BARE_EXCEPT."""
        rule = BareExceptRule()
        assert rule.rule_id == "PRACTICE_BARE_EXCEPT"


def test_bare_except_rule_registered(registry: dict[str, list[type]]) -> None:
    """BareExceptRule must be registered in the practices bucket."""
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert "BareExceptRule" in names
