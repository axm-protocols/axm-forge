"""Backend tools declare no output schema and answer the scoped client in text."""

from __future__ import annotations

import json
from typing import cast

import pytest
from axm import AXMTool, ToolResult
from axm.tools.write_scope import WriteContract
from starlette.testclient import TestClient

from axm_mcp import create_scoped_mcp_app

pytestmark = pytest.mark.integration

_HEADERS = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-06-18",
}


class PublicReadTool:
    """Return data, a prepared answer or a structural refusal."""

    def execute(self, *, mode: str, count: int = 2) -> ToolResult:
        if mode == "text":
            return ToolResult(success=True, data={"count": count}, text="**Ready**")
        if mode == "failure":
            return ToolResult(success=False, error="denied", text="Evidence")
        if mode == "raises":
            raise ValueError("broken fixture")
        return ToolResult(success=True, data={"available": True, "count": count})


async def unused_ui(name, arguments):
    raise AssertionError("No UI tool in this backend response probe")


def plain_dispatcher(*, word: str) -> dict[str, object]:
    """A legacy dispatcher returns its own object without a ToolResult envelope."""
    return {"echo": word}


@pytest.fixture
def backend_client(tmp_path):
    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"public_read", "plain_read"}),
        manifest=None,
        invoke=unused_ui,
        authorize=lambda scope: True,
        policy_revision="response-contract",
        tools={
            "public_read": cast(AXMTool, PublicReadTool()),
            "plain_read": cast(AXMTool, plain_dispatcher),
        },
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        yield client


def rpc(
    client: TestClient, method: str, params: dict[str, object]
) -> dict[str, object]:
    response = client.post(
        "/mcp",
        headers=_HEADERS,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json()["result"])


def test_backend_tools_declare_no_output_schema(backend_client):
    tools = rpc(backend_client, "tools/list", {})["tools"]
    declared = {tool["name"]: tool for tool in tools}
    assert "outputSchema" not in declared["public_read"]
    assert "outputSchema" not in declared["plain_read"]
    assert declared["public_read"]["inputSchema"]["title"] == "public_readArguments"
    assert declared["public_read"]["inputSchema"]["required"] == ["mode"]
    count = declared["public_read"]["inputSchema"]["properties"]["count"]
    assert count["type"] == "integer"
    assert declared["plain_read"]["inputSchema"]["title"] == "plain_readArguments"
    assert declared["plain_read"]["inputSchema"]["required"] == ["word"]


def test_data_only_result_answers_with_its_json_envelope(backend_client):
    result = rpc(
        backend_client,
        "tools/call",
        {"name": "public_read", "arguments": {"mode": "data", "count": 3}},
    )
    assert json.loads(result["content"][0]["text"]) == {
        "success": True,
        "available": True,
        "count": 3,
    }
    assert "structuredContent" not in result
    assert result["isError"] is False


def test_pre_rendered_text_is_the_whole_answer(backend_client):
    result = rpc(
        backend_client,
        "tools/call",
        {"name": "public_read", "arguments": {"mode": "text"}},
    )
    assert result["content"] == [{"type": "text", "text": "**Ready**"}]
    assert "structuredContent" not in result
    assert result["isError"] is False


def test_plain_dispatcher_answers_with_its_own_object(backend_client):
    result = rpc(
        backend_client,
        "tools/call",
        {"name": "plain_read", "arguments": {"word": "hello"}},
    )
    assert json.loads(result["content"][0]["text"]) == {"echo": "hello"}
    assert "structuredContent" not in result
    assert result["isError"] is False


@pytest.mark.parametrize("mode", ["failure", "raises"])
@pytest.mark.parametrize("facade", [False, True])
def test_failures_stay_structurally_failed(backend_client, mode, facade):
    arguments = {"mode": mode}
    name = "public_read"
    if facade:
        name = "axm_call"
        arguments = {"name": "public_read", "arguments": arguments}
    result = rpc(backend_client, "tools/call", {"name": name, "arguments": arguments})
    assert result["isError"] is True
    assert "structuredContent" not in result
    text = result["content"][0]["text"]
    if mode == "failure":
        assert text == "\u2717 denied\nEvidence"
    else:
        assert json.loads(text)["success"] is False
        assert "broken fixture" in text
