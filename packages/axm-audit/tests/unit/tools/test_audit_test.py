"""Unit tests for AuditTestTool MCP tool."""

from __future__ import annotations

import pytest

from axm_audit.tools.audit_test import AuditTestTool


class TestAuditTestTool:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_name(self) -> None:
        assert self.tool.name == "audit_test"


class TestAuditTestToolInvalidPath:
    def setup_method(self) -> None:
        self.tool = AuditTestTool()

    def test_internal_exception_returns_error_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nominal failure path: a crash inside run_tests becomes
        ``ToolResult(success=False, error=...)`` with a readable message,
        never an unhandled raise.

        Pure unit: ``Path.is_dir`` is stubbed True so the tool reaches the
        (patched, raising) ``run_tests`` without touching the filesystem.
        """

        def _boom(*_a: object, **_kw: object) -> object:
            raise RuntimeError("runner exploded")

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_tests", _boom, raising=False
        )
        monkeypatch.setattr(
            "axm_audit.tools.audit_test.Path.is_dir", lambda _self: True
        )

        result = AuditTestTool().execute(path="/virtual/project")

        assert result.success is False
        assert result.error is not None
        assert "runner exploded" in result.error

    def test_invalid_path(self) -> None:
        result = self.tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False
        assert "Not a directory" in (result.error or "")
