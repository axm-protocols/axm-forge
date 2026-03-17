"""AXM MCP Server — Streamable HTTP transport.

Reuses the FastMCP instance from mcp_app and runs it over HTTP
instead of stdio, enabling a single persistent process for all
conversations.
"""

from __future__ import annotations

import os

from starlette.requests import Request
from starlette.responses import JSONResponse

from axm_mcp.mcp_app import mcp

__all__ = ["DEFAULT_PORT", "health_check", "serve"]

DEFAULT_PORT = 9427
_MIN_PORT = 1
_MAX_PORT = 65535


@mcp.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
async def health_check(request: Request) -> JSONResponse:
    """Return server health with registered tool count."""
    tools = mcp._tool_manager.list_tools()
    return JSONResponse({"status": "ok", "tools_count": len(tools)})


def serve(
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    """Start the MCP server with Streamable HTTP transport.

    Args:
        host: Bind address (default 127.0.0.1).
        port: Bind port. Falls back to AXM_MCP_PORT env var, then 9427.
    """
    if port is None:
        env_port = os.environ.get("AXM_MCP_PORT")
        port = int(env_port) if env_port else DEFAULT_PORT

    if not (_MIN_PORT <= port <= _MAX_PORT):
        msg = f"Invalid port {port}: must be between {_MIN_PORT} and {_MAX_PORT}"
        raise ValueError(msg)

    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="streamable-http")
