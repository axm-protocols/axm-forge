"""Tests for MCP auto-discovered bib tools — TDD RED phase.

Tests cover:
- Tool discovery from axm.tools entry points
- search_paper: happy path, empty query, API failure, limit param
- doi_to_bibtex: happy path, empty DOI, 404
- get_pdf: happy path, not open access, empty DOI
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm.services.tools.base import ToolResult

# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"


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
# search_paper MCP tool
# ─────────────────────────────────────────────────────────────────────────────

_SEARCH_TOOL = "axm_bib.tools.search_paper.SearchPaperTool"


class TestSearchPaperMCP:
    """MCP search_paper tool tests."""

    def test_search_paper_tool_exists(self) -> None:
        """search_paper is discoverable from axm.tools."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "search_paper" in tools

    @patch(f"{_SEARCH_TOOL}.execute")
    def test_search_paper_happy_path(self, mock_exec: MagicMock) -> None:
        """Returns papers list."""
        mock_exec.return_value = ToolResult(
            success=True,
            data={
                "papers": [{"title": "Test", "doi": "10.1/x"}],
                "count": 1,
            },
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["search_paper"].execute(query="AI")
        assert result.success
        assert result.data["count"] == 1

    @patch(f"{_SEARCH_TOOL}.execute")
    def test_search_paper_empty_query(self, mock_exec: MagicMock) -> None:
        """Empty query returns error."""
        mock_exec.return_value = ToolResult(success=False, error="Query is required")
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["search_paper"].execute(query="")
        assert not result.success

    @patch(f"{_SEARCH_TOOL}.execute")
    def test_search_paper_api_failure(self, mock_exec: MagicMock) -> None:
        """Network error → success=False."""
        mock_exec.return_value = ToolResult(success=False, error="Connection refused")
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["search_paper"].execute(query="test")
        assert not result.success
        assert "Connection" in (result.error or "")

    @patch(f"{_SEARCH_TOOL}.execute")
    def test_search_paper_limit_param(self, mock_exec: MagicMock) -> None:
        """Limit is forwarded correctly."""
        mock_exec.return_value = ToolResult(
            success=True, data={"papers": [], "count": 0}
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        tools["search_paper"].execute(query="test", limit=3)
        mock_exec.assert_called_once_with(query="test", limit=3)


# ─────────────────────────────────────────────────────────────────────────────
# doi_to_bibtex MCP tool
# ─────────────────────────────────────────────────────────────────────────────

_DOI_TOOL = "axm_bib.tools.doi_to_bibtex.DoiBibtexTool"


class TestDoiToBibtexMCP:
    """MCP doi_to_bibtex tool tests."""

    def test_doi_to_bibtex_tool_exists(self) -> None:
        """doi_to_bibtex is discoverable."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "doi_to_bibtex" in tools

    @patch(f"{_DOI_TOOL}.execute")
    def test_doi_to_bibtex_happy_path(self, mock_exec: MagicMock) -> None:
        """Returns bibtex + key."""
        mock_exec.return_value = ToolResult(
            success=True,
            data={
                "bibtex": "@article{test, title={X}}",
                "key": "test2024",
                "doi": "10.1/x",
                "entry_type": "article",
            },
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["doi_to_bibtex"].execute(doi="10.1/x")
        assert result.success
        assert "@article" in result.data["bibtex"]

    @patch(f"{_DOI_TOOL}.execute")
    def test_doi_to_bibtex_empty_doi(self, mock_exec: MagicMock) -> None:
        """Empty DOI → error."""
        mock_exec.return_value = ToolResult(success=False, error="DOI is required")
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["doi_to_bibtex"].execute(doi="")
        assert not result.success

    @patch(f"{_DOI_TOOL}.execute")
    def test_doi_to_bibtex_not_found(self, mock_exec: MagicMock) -> None:
        """404 DOI → error."""
        mock_exec.return_value = ToolResult(success=False, error="404 Not Found")
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["doi_to_bibtex"].execute(doi="10.9999/nope")
        assert not result.success
        assert "404" in (result.error or "")


# ─────────────────────────────────────────────────────────────────────────────
# get_pdf MCP tool
# ─────────────────────────────────────────────────────────────────────────────

_PDF_TOOL = "axm_bib.tools.get_pdf.GetPdfTool"


class TestGetPdfMCP:
    """MCP get_pdf tool tests."""

    def test_get_pdf_tool_exists(self) -> None:
        """get_pdf is discoverable."""
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        assert "get_pdf" in tools

    @patch(f"{_PDF_TOOL}.execute")
    def test_get_pdf_happy_path(self, mock_exec: MagicMock) -> None:
        """Returns path + size."""
        mock_exec.return_value = ToolResult(
            success=True,
            data={
                "path": "/tmp/paper.pdf",
                "size_bytes": 42000,
                "is_open_access": True,
            },
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["get_pdf"].execute(doi="10.1/x")
        assert result.success
        assert result.data["is_open_access"] is True

    @patch(f"{_PDF_TOOL}.execute")
    def test_get_pdf_not_open_access(self, mock_exec: MagicMock) -> None:
        """Non-OA returns is_open_access=False."""
        mock_exec.return_value = ToolResult(
            success=True,
            data={
                "path": None,
                "is_open_access": False,
                "message": "Not open access",
            },
        )
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["get_pdf"].execute(doi="10.1/closed")
        assert result.success
        assert result.data["is_open_access"] is False

    @patch(f"{_PDF_TOOL}.execute")
    def test_get_pdf_empty_doi(self, mock_exec: MagicMock) -> None:
        """Empty DOI → error."""
        mock_exec.return_value = ToolResult(success=False, error="DOI is required")
        from axm_mcp.discovery import discover_tools

        tools = discover_tools()
        result = tools["get_pdf"].execute(doi="")
        assert not result.success
