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

import json
import os
import time
from collections.abc import Mapping
from contextvars import ContextVar
from typing import TypedDict, Unpack, cast

from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER, EventStore
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from axm_mcp.discovery import (
    ToolEntry,
    discover_tools,
    register_list_tools,
    register_one,
    register_tools,
)
from axm_mcp.facade import ToolCatalog
from axm_mcp.facade.tools import FACADE_TOOLS, register_facade
from axm_mcp.session_contracts import (
    SessionContractRegistry,
    UnboundSessionError,
    WriteContract,
)
from axm_mcp.settings import resolve_serve_mode
from axm_mcp.verify import VerifyTool
from axm_mcp.web_fetch import WebFetchTool


def _facade_enabled() -> bool:
    """Whether the compact facade is active (default: yes)."""
    return os.environ.get("AXM_MCP_FACADE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


# MCPServer server instance
_current_session_id = ContextVar[str | None]("axm_mcp_current_session_id", default=None)
session_contract_registry = SessionContractRegistry(clock=time.monotonic)


_WRITE_CONTRACT_HEADER = "X-AXM-Write-Contract"


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    folded_name = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == folded_name),
        None,
    )


def session_id_from_headers(headers: Mapping[str, str]) -> str:
    """Return the MCP session identity carried by request headers."""
    session_id = _header_value(headers, MCP_SESSION_ID_HEADER)
    if session_id is None:
        raise UnboundSessionError("no current MCP session identity")
    return session_id


__all__ = ["build_http_app"]


class _SessionContractMiddleware:
    """Bind per-session write contracts before MCP request dispatch."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        token = None
        try:
            token = _current_session_id.set(session_id_from_headers(headers))
        except UnboundSessionError:
            pass
        if headers.get(_WRITE_CONTRACT_HEADER) is not None:
            try:
                bind_session_from_headers(headers)
            except (UnboundSessionError, ValueError):
                pass
        try:
            await self._app(scope, receive, send)
        finally:
            if token is not None:
                _current_session_id.reset(token)


class _HttpAppOptions(TypedDict, total=False):
    """The keyword options mcp 2.x's transport passes to streamable_http_app."""

    streamable_http_path: str
    json_response: bool
    stateless_http: bool
    event_store: EventStore | None
    retry_interval: int | None
    max_request_body_size: int
    session_idle_timeout: float | None
    max_sessions: int | None
    transport_security: TransportSecuritySettings | None
    host: str


class _SessionAwareMCPServer(MCPServer[object]):
    """MCPServer variant whose HTTP transport binds shared-session contracts."""

    def streamable_http_app(self, **kwargs: Unpack[_HttpAppOptions]) -> Starlette:
        # mcp 2.x calls this with transport keywords (streamable_http_path,
        # json_response, session_idle_timeout...). A no-arg override compiles
        # and passes every unit test, then fails at boot when the transport
        # supplies them -- so relay whatever the caller sent.
        app = super().streamable_http_app(**kwargs)
        if resolve_serve_mode() == "shared":
            app.add_middleware(_SessionContractMiddleware)
        return app


def build_http_app() -> ASGIApp:
    """Build the served HTTP app, binding contracts only in shared mode."""
    return mcp.streamable_http_app()


def bind_session_from_headers(headers: Mapping[str, str]) -> None:
    """Bind a declared write contract to its request session identity."""
    from axm_mcp.session_contracts import parse_write_contract_header

    session_id = session_id_from_headers(headers)
    raw_contract = _header_value(headers, _WRITE_CONTRACT_HEADER)
    if raw_contract is not None:
        normalized = WriteContract.from_json(raw_contract)
        normalized_header = json.dumps(
            {
                "execution_root": normalized.execution_root,
                "allowed_prefixes": normalized.allowed_prefixes,
                "markdown_only_prefixes": normalized.markdown_only_prefixes,
            }
        )
        session_contract_registry.bind(
            session_id,
            parse_write_contract_header(normalized_header),
        )


def contract_for_session_id(session_id: str) -> WriteContract:
    """Resolve the write contract attached to one MCP session identity."""
    return session_contract_registry.resolve(session_id)


def current_session_id() -> str:
    """Return the identity of the in-flight MCP HTTP request."""
    session_id = _current_session_id.get()
    if session_id is None:
        raise UnboundSessionError("no current MCP session identity")
    return session_id


def _on_session_start(
    *,
    registry: SessionContractRegistry | None = None,
    session_id: str | None = None,
    write_contract_json: str | None = None,
) -> None:
    """Bind a declared write contract when an MCP session starts."""
    if registry is not None and session_id is not None:
        _current_session_id.set(session_id)
        if write_contract_json is not None:
            registry.bind(session_id, WriteContract.from_json(write_contract_json))
        return
    if _current_session_id.get() is None:
        raise UnboundSessionError("no current MCP session identity")


def _on_session_end(*, registry: SessionContractRegistry, session_id: str) -> None:
    """Release a session contract when its MCP session ends."""
    registry.release(session_id)
    if _current_session_id.get() == session_id:
        _current_session_id.set(None)


def _resolve_session_contract() -> WriteContract:
    """Resolve the contract belonging to the current MCP session."""
    return contract_for_session_id(current_session_id())


_SHARED_MODE = os.environ.get("AXM_MCP_SHARED") == "1"

mcp = _SessionAwareMCPServer("axm-mcp")

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
    """Register direct tools with the shared-mode resolver used by the facade."""
    for name, tool in tools.items():
        register_one(
            mcp,
            name,
            tool,
            registration=(
                _SHARED_MODE,
                _resolve_session_contract if _SHARED_MODE else None,
            ),
        )


if _facade_enabled():
    # The catalog indexes the FULL surface — discovered tools AND the
    # built-ins — so ``axm_describe``/``axm_search`` see ``verify``/``web_fetch``
    # too (they are already exposed directly on the hot path, but the facade
    # must not claim they are "unknown"). Discovered tools win on name clash.
    catalog = ToolCatalog(
        {**_BUILTINS, **discovered_tools},
        shared_mode=_SHARED_MODE,
        write_contract_resolver=(_resolve_session_contract if _SHARED_MODE else None),
    )
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
