"""Tests for the decoupled FastMCP server configuration."""

from __future__ import annotations

import json

from axm_mcp import mcp_app


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_discovery_ran(self) -> None:
        """Tool discovery ran (may be empty if no axm-* packages installed)."""
        assert isinstance(mcp_app._discovered_tools, dict)

    def test_main_function_exists(self) -> None:
        """main() entry point exists."""
        assert callable(mcp_app.main)


class TestToolCatalogResource:
    """Tests for the axm://tools MCP resource."""

    def test_tool_catalog_function_exists(self) -> None:
        """_tool_catalog function is defined."""
        assert callable(mcp_app._tool_catalog)

    def test_tool_catalog_returns_valid_json(self) -> None:
        """_tool_catalog returns valid JSON with expected structure."""
        result = mcp_app._tool_catalog()
        data = json.loads(result)
        assert "tools" in data
        assert "count" in data
        assert isinstance(data["tools"], list)
        assert data["count"] == len(data["tools"])

    def test_tool_catalog_includes_meta_tools(self) -> None:
        """Catalog includes verify and list_tools meta-tools."""
        result = mcp_app._tool_catalog()
        data = json.loads(result)
        names = {t["name"] for t in data["tools"]}
        assert "verify" in names
        assert "list_tools" in names

    def test_tool_catalog_entries_have_required_keys(self) -> None:
        """Each catalog entry has name and description."""
        result = mcp_app._tool_catalog()
        data = json.loads(result)
        for entry in data["tools"]:
            assert "name" in entry
            assert "description" in entry
