from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient

from axm_mcp.tool_surface import ToolSurfaceMiddleware, ToolSurfaceServer


def test_facade_app_exposes_selected_discovered_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import axm_mcp.mcp_app as app_module
    from axm_mcp import discovery

    def cold_tool() -> str:
        return "cold-result"

    with monkeypatch.context() as patch:
        patch.setenv("AXM_MCP_FACADE", "1")
        patch.setattr(discovery, "discover_tools", lambda: {"cold_tool": cold_tool})
        app_module = importlib.reload(app_module)
        app = app_module.build_http_app()
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            headers = {
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "X-AXM-Tool-Surface": '["cold_tool"]',
            }
            init = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
            )
            assert init.status_code == 200
            headers["mcp-session-id"] = init.headers["mcp-session-id"]
            client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            listed = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                },
            )
            assert '"name":"cold_tool"' in listed.text.replace(" ", "")
            called = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "cold_tool", "arguments": {}},
                },
            )
            assert "cold-result" in called.text
    importlib.reload(app_module)


def test_streamable_http_exposes_only_selected_catalog_tools() -> None:
    server = ToolSurfaceServer("test")

    @server.tool()
    def visible() -> str:
        return "visible"

    hidden = ToolSurfaceServer("catalog")

    @hidden.tool()
    def selected() -> str:
        return "selected"

    server.set_catalog_server(hidden)
    app = server.streamable_http_app()
    app.add_middleware(ToolSurfaceMiddleware)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "X-AXM-Tool-Surface": json.dumps(["selected"]),
        }
        init = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert init.status_code == 200
        headers["mcp-session-id"] = init.headers["mcp-session-id"]
        client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )
        listed = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            },
        )
        assert '"name":"selected"' in listed.text.replace(" ", "")
        called = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "selected", "arguments": {}},
            },
        )
        assert "selected" in called.text


def test_sessions_isolate_empty_unknown_and_facade_targets() -> None:
    server = ToolSurfaceServer("test")

    @server.tool()
    def axm_call(name: str) -> str:
        return name

    @server.tool()
    def ordinary() -> str:
        return "ordinary"

    app = server.streamable_http_app()
    app.add_middleware(ToolSurfaceMiddleware)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:

        def session(surface: list[str] | None) -> dict[str, str]:
            headers = {
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            }
            if surface is not None:
                headers["X-AXM-Tool-Surface"] = json.dumps(surface)
            result = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
            )
            headers["mcp-session-id"] = result.headers["mcp-session-id"]
            client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            headers.pop("X-AXM-Tool-Surface", None)
            return headers

        empty = session([])
        facade = session(["axm_call"])
        unknown = session(["missing"])
        normal = session(None)

        def rpc(
            headers: dict[str, str],
            method: str,
            params: dict[str, object] | None = None,
        ) -> str:
            return client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": method,
                    "params": params or {},
                },
            ).text

        assert '"tools":[]' in rpc(empty, "tools/list").replace(" ", "")
        assert "unknown or unavailable tools: missing" in rpc(unknown, "tools/list")
        assert "ordinary" in rpc(normal, "tools/list")
        assert "ordinary" not in rpc(facade, "tools/list")
        denied = rpc(
            facade,
            "tools/call",
            {
                "name": "axm_call",
                "arguments": {"name": "ordinary"},
            },
        )
        assert "undeclared tool refused" in denied
        with ThreadPoolExecutor(max_workers=2) as executor:
            empty_result = executor.submit(rpc, empty, "tools/list")
            ordinary_result = executor.submit(rpc, normal, "tools/list")
            assert '"tools":[]' in empty_result.result().replace(" ", "")
            assert "ordinary" in ordinary_result.result()
