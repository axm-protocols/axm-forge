"""Unit tests for DuplicationRule — no real I/O."""

from __future__ import annotations


class TestDuplicationUnit:
    """Pure unit tests for DuplicationRule (no real I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be ARCH_DUPLICATION."""
        from axm_audit.core.rules.duplication import DuplicationRule

        rule = DuplicationRule()
        assert rule.rule_id == "ARCH_DUPLICATION"
