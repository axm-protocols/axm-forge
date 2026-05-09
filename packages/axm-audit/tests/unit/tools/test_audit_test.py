"""Unit tests for AuditTestTool MCP tool."""

from __future__ import annotations

from axm_audit.tools.audit_test import AuditTestTool


class TestAuditTestTool:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_name(self) -> None:
        assert self.tool.name == "audit_test"
