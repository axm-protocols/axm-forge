"""AXM MCP Server — Pure discovery shell.

Discovers all AXMTool entry points from installed packages
(e.g. axm, axm-bib, axm-formal) and exposes them as MCP tools.

Zero imports from axm core — fully decoupled.
"""

import json
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
@mcp.tool(name="verify")
def _verify_tool(**kwargs: Any) -> dict[str, Any]:
    """One-shot project verification: audit + init check + AST enrichment.

    Args:
        path: Path to project root to verify.
    """
    if list(kwargs.keys()) == ["kwargs"] and isinstance(kwargs["kwargs"], dict):
        kwargs = kwargs["kwargs"]
    path = kwargs.get("path", ".")
    return verify_project(str(path), _discovered_tools)


# ── MCP Resource: tool catalog ──────────────────────────────
@mcp.resource(
    "axm://tools",
    name="tool_catalog",
    description="Catalog of all registered AXM tools with names and descriptions.",
    mime_type="application/json",
)
def _tool_catalog() -> str:
    """Return JSON catalog of all registered AXM tools."""
    catalog = []
    for name, tool in sorted(_discovered_tools.items()):
        doc = (tool.execute.__doc__ or "").strip().split("\n")[0]
        catalog.append({"name": name, "description": doc})
    catalog.append({"name": "verify", "description": "One-shot project verification."})
    catalog.append(
        {"name": "list_tools", "description": "List all available AXM tools."}
    )
    catalog.sort(key=lambda t: t["name"])
    return json.dumps({"tools": catalog, "count": len(catalog)}, indent=2)


# Entry point for MCP CLI
def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
