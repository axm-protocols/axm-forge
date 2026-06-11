"""AXM MCP Server — discovery shell with a compact facade.

Discovers all AXMTool entry points from installed packages (e.g. axm,
axm-bib, axm-formal).  By default it exposes them through a compact
**facade** (``axm_search`` / ``axm_describe`` / ``axm_call`` /
``axm_capabilities``) plus a small *hot path* of tools that opt in via
``expose_directly = True`` — keeping the ``tools/list`` payload small.

Set ``AXM_MCP_FACADE=0`` to fall back to the legacy behaviour (register
every discovered tool directly), which makes the bascule reversible.

Imports from axm core are limited to ``axm.tools.base`` (shared types +
``tool_metadata``) — no business-tool implementations are imported here.
"""

from __future__ import annotations

import os
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
from axm_mcp.facade import ToolCatalog
from axm_mcp.facade.tools import FACADE_TOOLS, register_facade
from axm_mcp.verify import VerifyTool
from axm_mcp.web_fetch import WebFetchTool


def _facade_enabled() -> bool:
    """Whether the compact facade is active (default: yes)."""
    return os.environ.get("AXM_MCP_FACADE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Auto-discover and register tools from installed packages.
# Internal-public registry (no leading underscore): a legitimate seam that
# tests assert against without reaching into module-private state.
discovered_tools = discover_tools()

# Built-in meta-tools (verify, web_fetch) participate as AXMTool instances so
# they get the same dual-format treatment as discovered tools. They are always
# exposed directly (hot path) regardless of facade mode.
_BUILTINS: dict[str, ToolEntry] = {
    "verify": cast(ToolEntry, VerifyTool(discovered_tools)),
    "web_fetch": cast(ToolEntry, WebFetchTool()),
}

# Meta/built-in tool descriptions feeding the ``list_tools`` listing.
_EXTRA_TOOLS = {
    "verify": "One-shot project verification: audit + init check + AST enrichment.",
    "web_fetch": "Fetch web pages with anti-bot bypass (basic / dynamic / stealth).",
    "list_tools": "List all available AXM tools with their names and descriptions.",
}


def _register_direct(tools: dict[str, ToolEntry]) -> None:
    """Register each tool in *tools* as an individual MCP tool."""
    for name, tool in tools.items():
        register_one(mcp, name, tool)


if _facade_enabled():
    catalog = ToolCatalog(discovered_tools)
    # Hot path: tools that opt in via expose_directly, registered individually.
    _hot = {name: discovered_tools[name] for name in catalog.hot_path()}
    _register_direct(_hot)
    # Built-ins are always exposed directly.
    _register_direct(_BUILTINS)
    # The four facade meta-tools cover everything else.
    register_facade(mcp, catalog)
    # list_tools still enumerates the FULL surface so clients can discover
    # tools that are reachable only via the facade.
    register_list_tools(mcp, discovered_tools, {**_EXTRA_TOOLS, **FACADE_TOOLS})
else:
    # Legacy behaviour: expose every discovered tool directly.
    register_tools(mcp, discovered_tools)
    _register_direct(_BUILTINS)
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
