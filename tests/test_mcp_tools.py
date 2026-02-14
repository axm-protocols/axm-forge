"""Tests for MCP auto-discovered formal tools (esbmc, dafny, kind2).

These tools are now auto-discovered via axm.tools entry points from axm-formal.
All discovery is mocked to isolate from actual installed packages.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from axm.tools.base import ToolResult

_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"


def _make_ep(name: str, tool_instance: Any | None = None) -> MagicMock:
    """Build a fake entry-point that loads *tool_instance* (or a default)."""
    if tool_instance is None:
        tool_instance = MagicMock()
        tool_instance.name = name
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = MagicMock(return_value=tool_instance)
    return ep


class TestFormalToolsDiscovered:
    """Formal tools are discovered from axm-formal entry points."""

    @patch(_DISCOVER)
    def test_formal_esbmc_discovered(self, mock_eps: MagicMock) -> None:
        """formal_esbmc is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("formal_esbmc")]
        tools = discover_tools()
        assert "formal_esbmc" in tools

    @patch(_DISCOVER)
    def test_formal_dafny_discovered(self, mock_eps: MagicMock) -> None:
        """formal_dafny is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("formal_dafny")]
        tools = discover_tools()
        assert "formal_dafny" in tools

    @patch(_DISCOVER)
    def test_formal_kind2_discovered(self, mock_eps: MagicMock) -> None:
        """formal_kind2 is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("formal_kind2")]
        tools = discover_tools()
        assert "formal_kind2" in tools


class TestVerifyViaMCP:
    """Verify tool via auto-discovery (mocked)."""

    @patch(_DISCOVER)
    def test_verify_happy_path(self, mock_eps: MagicMock) -> None:
        """formal_esbmc returns success."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "formal_esbmc"
        tool.execute.return_value = ToolResult(success=True, data={"verified": True})
        mock_eps.return_value = [_make_ep("formal_esbmc", tool)]

        tools = discover_tools()
        result = tools["formal_esbmc"].execute(source_file="/tmp/test.c")
        assert result.success

    @patch(_DISCOVER)
    def test_verify_failure(self, mock_eps: MagicMock) -> None:
        """formal_esbmc returns verification failure."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "formal_esbmc"
        tool.execute.return_value = ToolResult(
            success=False, error="Verification failed: buffer overflow"
        )
        mock_eps.return_value = [_make_ep("formal_esbmc", tool)]

        tools = discover_tools()
        result = tools["formal_esbmc"].execute(source_file="/tmp/test.c")
        assert not result.success
        assert "buffer overflow" in (result.error or "")
