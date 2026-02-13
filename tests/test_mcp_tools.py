"""Tests for MCP auto-discovered formal tools (esbmc, dafny, kind2, pytest).

These tools are now auto-discovered via axm.tools entry points from axm-formal.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm.tools.base import ToolResult


class TestFormalToolsDiscovered:
    """Formal tools are discovered from axm-formal entry points."""

    def test_esbmc_discovered(self) -> None:
        """esbmc is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "esbmc" in tools

    def test_dafny_discovered(self) -> None:
        """dafny is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "dafny" in tools

    def test_kind2_discovered(self) -> None:
        """kind2 is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "kind2" in tools

    def test_pytest_discovered(self) -> None:
        """pytest runner is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "pytest" in tools


_ESBMC = "axm_formal.tools.esbmc_runner.ESBMCTool"


class TestVerifyViaMCP:
    """Verify tool via auto-discovery."""

    @patch(f"{_ESBMC}.execute")
    def test_verify_happy_path(self, mock_exec: MagicMock) -> None:
        """esbmc returns success."""
        mock_exec.return_value = ToolResult(success=True, data={"verified": True})
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["esbmc"].execute(source_file="/tmp/test.c")
        assert result.success

    @patch(f"{_ESBMC}.execute")
    def test_verify_failure(self, mock_exec: MagicMock) -> None:
        """esbmc returns verification failure."""
        mock_exec.return_value = ToolResult(
            success=False, error="Verification failed: buffer overflow"
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["esbmc"].execute(source_file="/tmp/test.c")
        assert not result.success
        assert "buffer overflow" in (result.error or "")
