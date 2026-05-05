"""Unit tests for FormattingRule (no I/O)."""

from __future__ import annotations


class TestFormattingRule:
    """Pure unit tests for FormattingRule."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_FORMAT."""
        from axm_audit.core.rules.quality import FormattingRule

        assert FormattingRule().rule_id == "QUALITY_FORMAT"
