"""Tests for the decoupled FastMCP server configuration."""

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
