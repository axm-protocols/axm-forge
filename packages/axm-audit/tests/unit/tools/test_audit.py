"""Unit test for AuditTool simple properties."""

from __future__ import annotations


def test_name_property() -> None:
    """Tool name should be 'audit'."""
    from axm_audit.tools.audit import AuditTool

    tool = AuditTool()
    assert tool.name == "audit"
