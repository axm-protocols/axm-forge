"""Closed, request-local MCP surfaces, pinned to the initialized session."""

from __future__ import annotations

import json
from contextvars import ContextVar
from http import HTTPStatus

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
from mcp_types import CallToolResult, InputRequiredResult, Tool
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ["TOOL_SURFACE_HEADER", "ToolSurfaceMiddleware", "ToolSurfaceServer"]

TOOL_SURFACE_HEADER = "X-AXM-Tool-Surface"
_surface = ContextVar[tuple[str, ...] | None]("axm_mcp_tool_surface", default=None)
_MAX_SESSIONS = 10_000


def _parse(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    value = json.loads(raw)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item and item.isidentifier() for item in value
    ):
        raise ValueError("tool surface must be a JSON array of tool names")
    return tuple(dict.fromkeys(value))


class ToolSurfaceMiddleware:
    """Bind an immutable allowlist; never share a request's policy globally."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._sessions: dict[str, tuple[str, ...]] = {}

    def _resolve(self, headers: Headers) -> tuple[str, ...] | None:
        declared = _parse(headers.get(TOOL_SURFACE_HEADER))
        session = headers.get(MCP_SESSION_ID_HEADER)
        bound = self._sessions.get(session or "")
        if bound is not None:
            if declared is not None and declared != bound:
                raise ValueError("session tool surface cannot change")
            return bound
        if (
            session is None
            and declared is not None
            and len(self._sessions) >= _MAX_SESSIONS
        ):
            raise ValueError("too many tool surface sessions")
        return declared

    def _bind(self, session: str, surface: tuple[str, ...]) -> None:
        # Policies must never expire ahead of a still-live MCP session.
        if len(self._sessions) >= _MAX_SESSIONS:
            raise ValueError("too many tool surface sessions")
        self._sessions[session] = surface

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        try:
            surface = self._resolve(headers)
        except (ValueError, TypeError) as exc:
            await PlainTextResponse(str(exc), status_code=400)(scope, receive, send)
            return
        token = _surface.set(surface)

        async def respond(message: Message) -> None:
            if message["type"] == "http.response.start" and surface is not None:
                session = Headers(raw=message["headers"]).get(MCP_SESSION_ID_HEADER)
                if session and headers.get(MCP_SESSION_ID_HEADER) is None:
                    self._bind(session, surface)
                if (
                    scope["method"] == "DELETE"
                    and HTTPStatus.OK <= message["status"] < HTTPStatus.MULTIPLE_CHOICES
                    and (closing := headers.get(MCP_SESSION_ID_HEADER))
                ):
                    self._sessions.pop(closing, None)
            await send(message)

        try:
            await self._app(scope, receive, respond)
        finally:
            _surface.reset(token)


class ToolSurfaceServer(MCPServer[object]):
    """Enforce the same declaration at tools/list and tools/call."""

    async def list_tools(self) -> list[Tool]:
        tools = await super().list_tools()
        allowed = _surface.get()
        return (
            tools
            if allowed is None
            else [tool for tool in tools if tool.name in allowed]
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
        context: Context[object, object] | None = None,
    ) -> CallToolResult | InputRequiredResult:
        allowed = _surface.get()
        if allowed is not None and name not in allowed:
            raise ToolError(f"undeclared tool refused: {name}")
        return await super().call_tool(name, arguments, context)
