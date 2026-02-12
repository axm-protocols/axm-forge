"""AXM MCP Server — Pure discovery shell.

Discovers all AXMTool entry points from installed packages
(e.g. axm, axm-bib, axm-formal) and exposes them as MCP tools.

Zero imports from axm core — fully decoupled.
"""

from mcp.server.fastmcp import FastMCP

from axm_mcp.discovery import discover_tools, register_tools

# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Auto-discover and register tools from installed packages
_discovered_tools = discover_tools()
register_tools(mcp, _discovered_tools)


# Entry point for MCP CLI
def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
