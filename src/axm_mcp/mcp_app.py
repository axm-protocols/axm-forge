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
    register_one,
    register_tools,
)
from axm_mcp.verify import VerifyTool

# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Auto-discover and register tools from installed packages
_discovered_tools = discover_tools()
register_tools(
    mcp,
    _discovered_tools,
    extra_tools={
        "verify": "One-shot project verification: audit + init check + AST enrichment.",
    },
)

# Register the verify meta-tool as an AXMTool instance so the dispatcher
# emits a dual-format ToolResult (compact text for the LLM, structured
# data for any future programmatic consumer).
register_one(
    mcp,
    "verify",
    cast(ToolEntry, VerifyTool(_discovered_tools)),
)


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
