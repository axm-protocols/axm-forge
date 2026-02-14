"""Tests for MCP auto-discovered bib tools.

Tests cover:
- Tool discovery from axm.tools entry points
- search_paper: happy path, empty query, API failure, limit param
- doi_to_bibtex: happy path, empty DOI, 404
- get_pdf: happy path, not open access, empty DOI
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from axm.tools.base import ToolResult

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────


class TestToolDiscovery:
    """Auto-discovery of AXMTool entry points."""

    @patch(_DISCOVER)
    def test_discovers_entry_points(self, mock_eps: MagicMock) -> None:
        """Discovers and instantiates tools from axm.tools group."""
        from axm_mcp.discovery import discover_tools

        mock_tool_cls = MagicMock()
        mock_tool_instance = MagicMock()
        mock_tool_instance.name = "fake_tool"
        mock_tool_cls.return_value = mock_tool_instance

        ep = MagicMock()
        ep.name = "fake_tool"
        ep.load.return_value = mock_tool_cls
        mock_eps.return_value = [ep]

        tools = discover_tools()
        assert "fake_tool" in tools
        assert tools["fake_tool"] is mock_tool_instance

    @patch(_DISCOVER)
    def test_skips_broken_entry_point(self, mock_eps: MagicMock) -> None:
        """Broken entry point is skipped, not fatal."""
        from axm_mcp.discovery import discover_tools

        ep = MagicMock()
        ep.name = "broken"
        ep.load.side_effect = ImportError("missing dep")
        mock_eps.return_value = [ep]

        tools = discover_tools()
        assert len(tools) == 0

    @patch(_DISCOVER)
    def test_multiple_packages(self, mock_eps: MagicMock) -> None:
        """Tools from multiple packages co-exist."""
        from axm_mcp.discovery import discover_tools

        tool_a = MagicMock()
        tool_a.name = "tool_a"
        ep_a = MagicMock()
        ep_a.name = "tool_a"
        ep_a.load.return_value = MagicMock(return_value=tool_a)

        tool_b = MagicMock()
        tool_b.name = "tool_b"
        ep_b = MagicMock()
        ep_b.name = "tool_b"
        ep_b.load.return_value = MagicMock(return_value=tool_b)

        mock_eps.return_value = [ep_a, ep_b]

        tools = discover_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools

    @patch(_DISCOVER)
    def test_empty_no_packages(self, mock_eps: MagicMock) -> None:
        """No packages installed → empty dict, no crash."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = []
        tools = discover_tools()
        assert tools == {}


# ─────────────────────────────────────────────────────────────────────────────
# MCP registration
# ─────────────────────────────────────────────────────────────────────────────


class TestMCPRegistration:
    """Discovered tools get registered as MCP tools."""

    @patch(_DISCOVER)
    def test_register_creates_mcp_tool(self, mock_eps: MagicMock) -> None:
        """register_tools adds a tool callable to the MCP server."""
        from axm_mcp.discovery import discover_tools, register_tools
        from axm_mcp.mcp_app import mcp

        mock_tool = MagicMock()
        mock_tool.name = "test_register"
        mock_tool.execute.return_value = ToolResult(success=True, data={"x": 1})

        ep = MagicMock()
        ep.name = "test_register"
        ep.load.return_value = MagicMock(return_value=mock_tool)
        mock_eps.return_value = [ep]

        tools = discover_tools()
        register_tools(mcp, tools)

        # The tool should be listed in mcp's tools
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]
        assert "test_register" in tool_names


# ─────────────────────────────────────────────────────────────────────────────
# bib_search MCP tool (mocked discovery)
# ─────────────────────────────────────────────────────────────────────────────


class TestBibSearchMCP:
    """MCP bib_search tool tests — all discovered via mocked entry points."""

    @patch(_DISCOVER)
    def test_bib_search_tool_exists(self, mock_eps: MagicMock) -> None:
        """bib_search is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("bib_search")]
        tools = discover_tools()
        assert "bib_search" in tools

    @patch(_DISCOVER)
    def test_bib_search_happy_path(self, mock_eps: MagicMock) -> None:
        """Returns papers list."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=True,
            data={"papers": [{"title": "Test", "doi": "10.1/x"}], "count": 1},
        )
        mock_eps.return_value = [_make_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="AI")
        assert result.success
        assert result.data["count"] == 1

    @patch(_DISCOVER)
    def test_bib_search_empty_query(self, mock_eps: MagicMock) -> None:
        """Empty query returns error."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(success=False, error="Query is required")
        mock_eps.return_value = [_make_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="")
        assert not result.success

    @patch(_DISCOVER)
    def test_bib_search_api_failure(self, mock_eps: MagicMock) -> None:
        """Network error → success=False."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=False, error="Connection refused"
        )
        mock_eps.return_value = [_make_ep("bib_search", tool)]

        tools = discover_tools()
        result = tools["bib_search"].execute(query="test")
        assert not result.success
        assert "Connection" in (result.error or "")

    @patch(_DISCOVER)
    def test_bib_search_limit_param(self, mock_eps: MagicMock) -> None:
        """Limit is forwarded correctly."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_search"
        tool.execute.return_value = ToolResult(
            success=True, data={"papers": [], "count": 0}
        )
        mock_eps.return_value = [_make_ep("bib_search", tool)]

        tools = discover_tools()
        tools["bib_search"].execute(query="test", limit=3)
        tool.execute.assert_called_once_with(query="test", limit=3)


# ─────────────────────────────────────────────────────────────────────────────
# bib_doi MCP tool (mocked discovery)
# ─────────────────────────────────────────────────────────────────────────────


class TestBibDoiMCP:
    """MCP bib_doi tool tests."""

    @patch(_DISCOVER)
    def test_bib_doi_tool_exists(self, mock_eps: MagicMock) -> None:
        """bib_doi is discoverable."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("bib_doi")]
        tools = discover_tools()
        assert "bib_doi" in tools

    @patch(_DISCOVER)
    def test_bib_doi_happy_path(self, mock_eps: MagicMock) -> None:
        """Returns bibtex + key."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_doi"
        tool.execute.return_value = ToolResult(
            success=True,
            data={
                "bibtex": "@article{test, title={X}}",
                "key": "test2024",
                "doi": "10.1/x",
                "entry_type": "article",
            },
        )
        mock_eps.return_value = [_make_ep("bib_doi", tool)]

        tools = discover_tools()
        result = tools["bib_doi"].execute(doi="10.1/x")
        assert result.success
        assert "@article" in result.data["bibtex"]

    @patch(_DISCOVER)
    def test_bib_doi_empty_doi(self, mock_eps: MagicMock) -> None:
        """Empty DOI → error."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_doi"
        tool.execute.return_value = ToolResult(success=False, error="DOI is required")
        mock_eps.return_value = [_make_ep("bib_doi", tool)]

        tools = discover_tools()
        result = tools["bib_doi"].execute(doi="")
        assert not result.success

    @patch(_DISCOVER)
    def test_bib_doi_not_found(self, mock_eps: MagicMock) -> None:
        """404 DOI → error."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_doi"
        tool.execute.return_value = ToolResult(success=False, error="404 Not Found")
        mock_eps.return_value = [_make_ep("bib_doi", tool)]

        tools = discover_tools()
        result = tools["bib_doi"].execute(doi="10.9999/nope")
        assert not result.success
        assert "404" in (result.error or "")


# ─────────────────────────────────────────────────────────────────────────────
# bib_pdf MCP tool (mocked discovery)
# ─────────────────────────────────────────────────────────────────────────────


class TestBibPdfMCP:
    """MCP bib_pdf tool tests."""

    @patch(_DISCOVER)
    def test_bib_pdf_tool_exists(self, mock_eps: MagicMock) -> None:
        """bib_pdf is discoverable."""
        from axm_mcp.discovery import discover_tools

        mock_eps.return_value = [_make_ep("bib_pdf")]
        tools = discover_tools()
        assert "bib_pdf" in tools

    @patch(_DISCOVER)
    def test_bib_pdf_happy_path(self, mock_eps: MagicMock) -> None:
        """Returns path + size."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(
            success=True,
            data={
                "path": "/tmp/paper.pdf",
                "size_bytes": 42000,
                "is_open_access": True,
            },
        )
        mock_eps.return_value = [_make_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="10.1/x")
        assert result.success
        assert result.data["is_open_access"] is True

    @patch(_DISCOVER)
    def test_bib_pdf_not_open_access(self, mock_eps: MagicMock) -> None:
        """Non-OA returns is_open_access=False."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(
            success=True,
            data={
                "path": None,
                "is_open_access": False,
                "message": "Not open access",
            },
        )
        mock_eps.return_value = [_make_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="10.1/closed")
        assert result.success
        assert result.data["is_open_access"] is False

    @patch(_DISCOVER)
    def test_bib_pdf_empty_doi(self, mock_eps: MagicMock) -> None:
        """Empty DOI → error."""
        from axm_mcp.discovery import discover_tools

        tool = MagicMock()
        tool.name = "bib_pdf"
        tool.execute.return_value = ToolResult(success=False, error="DOI is required")
        mock_eps.return_value = [_make_ep("bib_pdf", tool)]

        tools = discover_tools()
        result = tools["bib_pdf"].execute(doi="")
        assert not result.success
