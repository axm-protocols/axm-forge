"""Tests for AuditTestTool MCP tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from axm_audit.tools.audit_test import AuditTestTool


class TestAuditTestTool:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    @patch("axm_audit.core.test_runner.run_tests")
    def test_execute_success(self, mock_run: MagicMock, tmp_path: Any) -> None:
        from axm_audit.core.test_runner import TestReport

        mock_run.return_value = TestReport(
            passed=42, failed=0, duration=5.0, coverage=91.0
        )

        result = self.tool.execute(path=str(tmp_path))
        assert result.success is True
        assert result.data is not None
        assert result.data["passed"] == 42
        assert result.data["coverage"] == 91.0
