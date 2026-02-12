"""AXM MCP Server — Runtime execution for the AXM protocol ecosystem."""

from axm_mcp._version import __version__

__all__ = ["__version__", "main"]


def main() -> None:
    """Entry point for axm-mcp command."""
    from axm_mcp.mcp_app import mcp

    mcp.run()
