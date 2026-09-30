"""The session surface is both the visible API and the enforced call boundary."""

from __future__ import annotations

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from axm_mcp.tool_surface import ToolSurfaceMiddleware, ToolSurfaceServer

pytestmark = pytest.mark.integration


def test_direct_surface_hides_facade_and_refuses_undeclared_calls() -> None:
    server = ToolSurfaceServer("test")

    @server.tool()
    def ast_inspect() -> str:
        return "source"

    @server.tool()
    def axm_call() -> str:
        return "facade"

    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        names = [tool.name for tool in await server.list_tools()]
        rejected = False
        try:
            await server.call_tool("axm_call", {})
        except ToolError:
            rejected = True
        body = json.dumps({"names": names, "rejected": rejected}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"mcp-session-id", b"test-session"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    client = TestClient(ToolSurfaceMiddleware(endpoint))
    result = client.post("/", headers={"X-AXM-Tool-Surface": '["ast_inspect"]'})
    assert result.json() == {"names": ["ast_inspect"], "rejected": True}
    bound = client.post("/", headers={"mcp-session-id": "test-session"})
    assert bound.json() == result.json()
    elevated = client.post(
        "/",
        headers={
            "mcp-session-id": "test-session",
            "X-AXM-Tool-Surface": '["axm_call"]',
        },
    )
    assert elevated.status_code == 400
    ordinary = client.post("/")
    assert ordinary.json()["names"] == ["ast_inspect", "axm_call"]


def test_invalid_surface_is_rejected_before_dispatch() -> None:
    async def never(scope: Scope, receive: Receive, send: Send) -> None:
        raise AssertionError("malformed policy reached dispatch")

    client = TestClient(ToolSurfaceMiddleware(never))
    assert client.post("/", headers={"X-AXM-Tool-Surface": "{}"}).status_code == 400
