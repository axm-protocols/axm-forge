"""Unit tests for BlockingIORule (pure)."""

from __future__ import annotations

from axm_audit.core.rules.practices.blocking_io import BlockingIORule


class TestBlockingIORuleUnit:
    """Tests for BlockingIORule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BLOCKING_IO."""
        rule = BlockingIORule()
        assert rule.rule_id == "PRACTICE_BLOCKING_IO"


def test_blocking_io_rule_registered(registry: dict[str, list[type]]) -> None:
    """BlockingIORule must be registered in the practices bucket."""
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert "BlockingIORule" in names
