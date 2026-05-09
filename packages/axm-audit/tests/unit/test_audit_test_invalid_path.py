"""Integration test for AuditTestTool with an invalid path."""

from __future__ import annotations

from axm_audit.tools.audit_test import AuditTestTool


class TestAuditTestToolInvalidPath:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_invalid_path(self) -> None:
        result = self.tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False
        assert "Not a directory" in (result.error or "")
