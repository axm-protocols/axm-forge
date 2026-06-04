"""AXM MCP Server — Pure discovery shell.

Discovers all AXMTool entry points from installed packages
(e.g. axm, axm-bib, axm-formal) and exposes them as MCP tools.

Zero imports from axm core — fully decoupled.
"""

from __future__ import annotations

from typing import cast

from mcp.server.fastmcp import FastMCP

import axm_mcp.wrapping as _wrapping
from axm_mcp.discovery import (
    ToolEntry,
    discover_tools,
    register_list_tools,
    register_one,
    register_tools,
)
from axm_mcp.verify import VerifyTool
from axm_mcp.web_fetch import WebFetchTool

# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Auto-discover and register tools from installed packages.
# Internal-public registry (no leading underscore): a legitimate seam that
# tests assert against without reaching into module-private state.
discovered_tools = discover_tools()

# Meta/built-in tools registered manually (not entry-point discovered).
# Their names + descriptions feed the ``list_tools`` meta-tool listing.
_EXTRA_TOOLS = {
    "verify": "One-shot project verification: audit + init check + AST enrichment.",
    "web_fetch": "Fetch web pages with anti-bot bypass (basic / dynamic / stealth).",
    "list_tools": "List all available AXM tools with their names and descriptions.",
}

register_tools(mcp, discovered_tools, extra_tools=_EXTRA_TOOLS)

# Register the verify meta-tool as an AXMTool instance so the dispatcher
# emits a dual-format ToolResult (compact text for the LLM, structured
# data for any future programmatic consumer).
register_one(
    mcp,
    "verify",
    cast(ToolEntry, VerifyTool(discovered_tools)),
)

# Register the web_fetch built-in tool (async fetch bridged to a sync
# execute() seam by WebFetchTool).
register_one(
    mcp,
    "web_fetch",
    cast(ToolEntry, WebFetchTool()),
)

# Register the list_tools meta-tool so MCP clients can enumerate the full
# tool surface (discovered + built-in) at runtime.
register_list_tools(mcp, discovered_tools, _EXTRA_TOOLS)


# Entry point for MCP CLI
def main(*, http: bool = False) -> None:
    """Run the MCP server.

    Args:
        http: When True, enable HTTP-mode warnings for implicit paths.
    """
    _wrapping._HTTP_MODE = http
    mcp.run()


if __name__ == "__main__":
    main()
