"""AXM MCP Server — Streamable HTTP transport.

Reuses the MCPServer instance from mcp_app and runs it over HTTP
instead of stdio, enabling a single persistent process for all
conversations.
"""

from __future__ import annotations

from collections.abc import Callable

from axm.tools.write_scope import WriteContract
from starlette.requests import Request
from starlette.responses import JSONResponse

import axm_mcp.wrapping as _wrapping
from axm_mcp.mcp_app import mcp
from axm_mcp.settings import HEALTH_PATH, ServeMode, resolve_http_port

__all__ = ["health_check", "serve"]

_MIN_PORT = 1
_MAX_PORT = 65535

# The serving policy this process resolved, recorded by ``serve`` before the
# transport starts. ``/health`` reports it, and whether write contracts are
# enforced is derived from it alone — never from a second flag.
_SERVE_MODE: ServeMode = "dedicated"


class SharedModeNotArmedError(RuntimeError):
    """Raised when shared serving lacks a per-session contract resolver."""


@mcp.custom_route(HEALTH_PATH, methods=["GET"])  # type: ignore[untyped-decorator]
async def health_check(request: Request) -> JSONResponse:
    """Return server health with registered tool count.

    Reads the count from MCPServer's public ``list_tools()`` enumeration,
    which reflects exactly what is registered on the instance in BOTH
    facade and legacy modes — no private ``_tool_manager`` access and no
    parallel counter that could drift from the registration seam.
    """
    tools = await mcp.list_tools()
    return JSONResponse(
        {
            "status": "ok",
            "tools_count": len(tools),
            "serve_mode": _SERVE_MODE,
            "write_contracts_enforced": _SERVE_MODE == "shared",
        }
    )


def serve(
    host: str = "127.0.0.1",
    port: int | None = None,
    *,
    shared: bool = False,
    session_resolver: Callable[[], WriteContract | None] | None = None,
) -> None:
    """Start the MCP server with Streamable HTTP transport.

    Args:
        host: Bind address (default 127.0.0.1).
        port: Bind port. When omitted, the package's shared resolution
            seam decides it for the active state profile — the historical
            ``AXM_MCP_PORT`` still wins there, through the upstream alias
            registry rather than a local read that would race it.
    """
    if shared and session_resolver is None:
        raise SharedModeNotArmedError(
            "shared mode requires an armed per-session contract resolver"
        )

    if port is None:
        port = resolve_http_port()

    if not (_MIN_PORT <= port <= _MAX_PORT):
        msg = f"Invalid port {port}: must be between {_MIN_PORT} and {_MAX_PORT}"
        raise ValueError(msg)

    # HTTP mode is the single long-running shared process: enable per-key
    # concurrency locks (KeyedLock) and implicit-path warnings before the
    # server starts. Stdio mode (cli._stdio) leaves this False — one process
    # per conversation, no cross-session contention. This boundary is the
    # single writer of _HTTP_MODE=True in production.
    global _SERVE_MODE
    _SERVE_MODE = "shared" if shared else "dedicated"
    _wrapping._HTTP_MODE = True
    mcp.run(transport="streamable-http", host=host, port=port)
