"""AXM MCP Server — Pure discovery shell.

Discovers all AXMTool entry points from installed packages
(e.g. axm, axm-bib, axm-formal) and exposes them as MCP tools.

Zero imports from axm core — fully decoupled.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from axm_mcp.discovery import discover_tools, register_tools
from axm_mcp.verify import verify_project

# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Auto-discover and register tools from installed packages
_discovered_tools = discover_tools()
register_tools(
    mcp,
    _discovered_tools,
    extra_tools={
        "verify": "One-shot project verification: audit + init check + AST enrichment."
    },
)


# Register the verify meta-tool
@mcp.tool(name="verify")  # type: ignore[misc]
def _verify_tool(**kwargs: Any) -> dict[str, Any]:
    """One-shot project verification: audit + init check + AST enrichment.

    Args:
        path: Path to project root to verify.
    """
    if list(kwargs.keys()) == ["kwargs"] and isinstance(kwargs["kwargs"], dict):
        kwargs = kwargs["kwargs"]
    path = kwargs.get("path", ".")
    return verify_project(str(path), _discovered_tools)


# Entry point for MCP CLI
def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
