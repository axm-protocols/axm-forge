"""Transport contract: a ToolResult's text is the client's whole answer.

Route by route (shared server direct and facade, scoped app direct and facade),
an MCP client receives the prepared ``text`` of a ToolResult and nothing of its
``data``, in ``content`` as in ``structuredContent``. A large synthetic payload
measures that nothing leaks: clients that display structured data instead of
text (Claude Code does) would otherwise put it in the model's context.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import cast

import pytest
from axm import AXMTool, ToolResult
from axm.tools.write_scope import WriteContract
from mcp.server.mcpserver import MCPServer
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from axm_mcp import create_scoped_mcp_app
from axm_mcp.discovery import ToolEntry, register_one
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade

pytestmark = pytest.mark.integration

_HEADERS = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-06-18",
}
_MARKER = "payload-row"
_DATA = {"rows": [{"id": i, "label": f"{_MARKER}-{i:06d}" * 5} for i in range(1000)]}
_TEXT = {"success": "compact sheet", "failure": "compact diagnostic"}
_FAILURE_TEXT = "✗ denied\ncompact diagnostic"
# The answer is the text plus the JSON-RPC envelope; the data is ~100 KB.
_MAX_ANSWER = 1_000


class SheetTool:
    """Return a large structured sheet alongside its compact model text."""

    def execute(self, *, outcome: str = "success") -> ToolResult:
        if outcome == "failure":
            return ToolResult(
                success=False, error="denied", data=_DATA, text=_TEXT[outcome]
            )
        return ToolResult(success=True, data=_DATA, text=_TEXT[outcome])


async def _unused_ui(name: str, arguments: dict[str, object]) -> ToolResult:
    raise AssertionError("no UI tool in this transport contract")


def _shared_app() -> ASGIApp:
    server = MCPServer("shared contract")
    register_one(server, "sheet", cast(AXMTool, SheetTool()))
    register_facade(server, ToolCatalog({"sheet": cast(ToolEntry, SheetTool())}))
    return server.streamable_http_app(stateless_http=True, json_response=True)


def _scoped_app(root: str) -> ASGIApp:
    return create_scoped_mcp_app(
        allowed_tools=frozenset({"sheet"}),
        manifest=None,
        invoke=_unused_ui,
        authorize=lambda scope: True,
        policy_revision="transport-contract",
        tools={"sheet": cast(AXMTool, SheetTool())},
        write_contract=WriteContract.from_mapping({"execution_root": root}),
    )


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _call(app: ASGIApp, facade: bool, outcome: str) -> tuple[dict[str, object], int]:
    arguments: dict[str, object] = {"outcome": outcome}
    params: dict[str, object] = (
        {"name": "axm_call", "arguments": {"name": "sheet", "arguments": arguments}}
        if facade
        else {"name": "sheet", "arguments": arguments}
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        response = client.post(
            "/mcp",
            headers=_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params},
        )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json()["result"]), len(response.content)


def test_synthetic_data_is_large_enough_to_prove_a_leak():
    assert len(json.dumps(_DATA)) > 100_000


@pytest.mark.parametrize("outcome", ["success", "failure"])
@pytest.mark.parametrize("facade", [False, True])
@pytest.mark.parametrize("route", ["shared", "scoped"])
def test_client_receives_the_text_and_none_of_the_data(
    tmp_path, route, facade, outcome
):
    app = _shared_app() if route == "shared" else _scoped_app(str(tmp_path))
    result, size = _call(app, facade, outcome)
    expected = _TEXT["success"] if outcome == "success" else _FAILURE_TEXT
    assert result["content"] == [{"type": "text", "text": expected}]
    structured = result.get("structuredContent")
    # The shared server mirrors the text as {"result": text}; no other value.
    assert set(_strings(structured)) <= {expected}, structured
    assert size < _MAX_ANSWER, f"{route} answer is {size} bytes"
    if route == "scoped":
        assert structured is None
        assert result["isError"] is (outcome == "failure")


def test_scoped_backend_tools_declare_no_output_schema(tmp_path):
    with TestClient(
        _scoped_app(str(tmp_path)), base_url="http://127.0.0.1:9427"
    ) as client:
        response = client.post(
            "/mcp",
            headers=_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
    assert "outputSchema" not in tools["sheet"]
