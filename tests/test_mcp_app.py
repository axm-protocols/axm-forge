"""Tests for the decoupled FastMCP server configuration."""

from axm_mcp import mcp_app


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_server_has_discovered_tools(self) -> None:
        """Server has auto-discovered tools registered."""
        # At minimum, the axm core tools should be discovered
        # (init, check, resume, read) if axm is installed
        assert len(mcp_app._discovered_tools) > 0

    def test_main_function_exists(self) -> None:
        """main() entry point exists."""
        assert callable(mcp_app.main)
