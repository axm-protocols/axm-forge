"""Scoped MCP uses identical permissions for direct and facade traffic."""

from __future__ import annotations

import json
from typing import cast

import pytest
from axm import AXMTool, ToolResult, load_declarative_manifest, tool_scope_sha256
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from axm_mcp import create_scoped_mcp_app

pytestmark = pytest.mark.integration
_HEADERS = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-06-18",
    "authorization": "Bearer bound",
}
_NAME = "rugby_ui_select_match"


@pytest.fixture
def manifest():
    return load_declarative_manifest(
        {
            "schema_version": 1,
            "addon_id": "rugby",
            "bundle_sha256": "a" * 64,
            "tools": [
                {
                    "name": _NAME,
                    "handler": _NAME,
                    "description": "Select a match",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"match": {"type": "string"}},
                        "required": ["match"],
                        "additionalProperties": False,
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {"match": {"type": "string"}},
                        "required": ["match"],
                        "additionalProperties": False,
                    },
                }
            ],
        }
    )


@pytest.fixture
def runtime(manifest):
    state = {"authorized": True, "calls": []}

    async def invoke(name, arguments):
        state["calls"].append((name, arguments))
        return ToolResult(success=True, data=arguments)

    def authorize(scope):
        headers = dict(scope["headers"])
        return state["authorized"] and headers.get(b"authorization") == b"Bearer bound"

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({_NAME}),
        manifest=manifest,
        invoke=invoke,
        authorize=authorize,
        policy_revision="r1",
        tools={},
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        yield client, state


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


@pytest.mark.parametrize("policy", ["sync_live", "sync_revoked", "async"])
def test_sync_nested_dispatch_on_ui_event_loop_is_explicit_and_fail_closed(
    manifest, tmp_path, policy
):
    from axm.tools import load_tool, override_tools
    from axm.tools.write_scope import WriteContract

    live = {"authorized": True}
    effects = []

    class Tool:
        name = "fixture_backend"

        def execute(self) -> ToolResult:
            effects.append("observed")
            return ToolResult(success=True, data={"match": "A"})

    def authorize(scope) -> bool:
        return live["authorized"]

    async def async_authorize(scope) -> bool:
        return live["authorized"]

    async def invoke(name, arguments):
        if policy == "sync_revoked":
            live["authorized"] = False
        return load_tool("fixture_backend").execute()

    backend = cast(AXMTool, Tool())
    app = create_scoped_mcp_app(
        allowed_tools=frozenset({_NAME, "fixture_backend"}),
        manifest=manifest,
        invoke=invoke,
        authorize=async_authorize if policy == "async" else authorize,
        policy_revision="ui-loop-review",
        tools={"fixture_backend": backend},
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with override_tools({"fixture_backend": backend}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            result = rpc(
                client,
                "tools/call",
                {
                    "name": _NAME,
                    "arguments": {"match": "A"},
                },
            )
    assert result["isError"] is (policy != "sync_live")
    assert effects == (["observed"] if policy == "sync_live" else [])
    if policy == "async":
        assert "requires a worker thread" in str(result["content"])


def test_exact_schema_and_shared_direct_facade(runtime, manifest):
    client, state = runtime
    tools = rpc(client, "tools/list", {})["tools"]
    item = next(tool for tool in tools if tool["name"] == _NAME)
    assert item["inputSchema"] == manifest.tools[0].input_schema
    assert item["outputSchema"] == manifest.tools[0].output_schema
    direct = rpc(client, "tools/call", {"name": _NAME, "arguments": {"match": "A"}})
    facade = rpc(
        client,
        "tools/call",
        {"name": "axm_call", "arguments": {"name": _NAME, "arguments": {"match": "B"}}},
    )
    assert direct["structuredContent"] == {"match": "A"}
    assert facade["structuredContent"] == {"match": "B"}
    assert state["calls"] == [(_NAME, {"match": "A"}), (_NAME, {"match": "B"})]


@pytest.mark.parametrize("target", ["not_allowed", "axm_call"])
def test_direct_and_nested_facade_deny(runtime, target):
    client, state = runtime
    result = rpc(
        client, "tools/call", {"name": "axm_call", "arguments": {"name": target}}
    )
    assert result["isError"]
    assert state["calls"] == []


def test_undeclared_arguments_never_reach_view(runtime):
    client, state = runtime
    result = rpc(
        client,
        "tools/call",
        {"name": _NAME, "arguments": {"match": "A", "target": "other-view"}},
    )
    assert result["isError"]
    assert state["calls"] == []


def test_facade_discovery_is_filtered(runtime):
    client, _ = runtime
    result = rpc(client, "tools/call", {"name": "axm_search", "arguments": {}})
    data = json.loads(result["content"][0]["text"])
    assert [tool["name"] for tool in data] == [_NAME]
    denied = rpc(
        client, "tools/call", {"name": "axm_describe", "arguments": {"name": "secret"}}
    )
    assert denied["isError"]


def test_health_and_client_headers_cannot_elevate(runtime):
    client, state = runtime
    health = client.get("/health", headers=_HEADERS)
    assert health.status_code == 200
    assert health.json() == {
        "kind": "axm-scoped-mcp",
        "schema_version": 1,
        "policy_revision": "r1",
        "tool_scope_sha256": tool_scope_sha256(frozenset({_NAME})),
        "write_contracts_enforced": False,
    }
    assert client.get("/health").status_code == 403
    response = client.post(
        "/mcp",
        headers={**_HEADERS, "X-AXM-Tool-Surface": '["secret"]'},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 200
    assert "secret" not in response.text
    state["authorized"] = False
    assert client.get("/health", headers=_HEADERS).status_code == 403
    assert client.post("/mcp", headers=_HEADERS, json={}).status_code == 403


@pytest.mark.asyncio
async def test_two_concurrent_scopes_keep_state_and_recheck_nested_names(manifest):
    import asyncio

    import httpx
    from axm.tools import load_tool
    from axm.tools.access import ToolAccessDenied

    observed = []

    def make_app(label: str) -> ASGIApp:
        async def invoke(name, arguments):
            with pytest.raises(ToolAccessDenied):
                load_tool("hidden")
            await asyncio.sleep(0)
            observed.append((label, arguments["match"]))
            return ToolResult(success=True, data=arguments)

        return create_scoped_mcp_app(
            allowed_tools=frozenset({_NAME}),
            manifest=manifest,
            invoke=invoke,
            authorize=lambda scope: True,
            policy_revision=label,
            tools={},
        )

    async def run(label: str) -> None:
        transport = httpx.ASGITransport(app=make_app(label))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:9427"
        ) as client:
            response = await client.post(
                "/mcp",
                headers=_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": _NAME, "arguments": {"match": label}},
                },
            )
            assert response.status_code == 200
            assert response.json()["result"]["structuredContent"] == {"match": label}

    await asyncio.gather(run("A"), run("B"))
    assert sorted(observed) == [("A", "A"), ("B", "B")]


def test_empty_scope_hides_and_refuses_facade(manifest):
    async def invoke(name, arguments):
        raise AssertionError("empty scope invoked")

    app = create_scoped_mcp_app(
        allowed_tools=frozenset(),
        manifest=manifest,
        invoke=invoke,
        authorize=lambda scope: True,
        policy_revision="empty",
        tools={},
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        assert rpc(client, "tools/list", {})["tools"] == []
        assert rpc(client, "tools/call", {"name": "axm_search"})["isError"]


def test_invalid_view_confirmation_is_rejected(manifest):
    async def invoke(name, arguments):
        return ToolResult(success=True, data={"wrong": "shape"})

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({_NAME}),
        manifest=manifest,
        invoke=invoke,
        authorize=lambda scope: True,
        policy_revision="r",
        tools={},
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        assert rpc(client, "tools/call", {"name": _NAME, "arguments": {"match": "A"}})[
            "isError"
        ]


def test_health_of_dynamic_mount_uses_adjacent_path(manifest):
    from starlette.applications import Starlette
    from starlette.routing import Mount

    async def invoke(name, arguments):
        return ToolResult(success=True, data=arguments)

    child = create_scoped_mcp_app(
        allowed_tools=frozenset({_NAME}),
        manifest=manifest,
        invoke=invoke,
        authorize=lambda scope: True,
        policy_revision="r",
        tools={},
    )
    root = Starlette(routes=[Mount("/cap/opaque", app=child)])
    with TestClient(root, base_url="http://127.0.0.1:9427") as client:
        assert client.get("/cap/opaque/health").json()["policy_revision"] == "r"
        response = client.post(
            "/cap/opaque/mcp",
            headers=_HEADERS,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 200
        assert _NAME in response.text


def test_backend_scope_requires_host_write_contract(manifest):
    class Backend:
        name = "backend"

        def execute(self, **kwargs):
            return ToolResult(success=True)

    async def invoke(name, arguments):
        raise AssertionError("backend contract missing")

    with pytest.raises(ValueError, match="host write contract"):
        create_scoped_mcp_app(
            allowed_tools=frozenset({"backend"}),
            manifest=manifest,
            invoke=invoke,
            authorize=lambda scope: True,
            policy_revision="r",
            tools={"backend": Backend()},
        )


def test_scoped_ui_cannot_inherit_ambient_write_contract(
    manifest, tmp_path, monkeypatch
):
    from axm import require_write_path
    from axm.tools.write_scope import WriteContract

    ambient = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": ["."],
        }
    )
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": ambient.execution_root,
                "allowed_prefixes": list(ambient.allowed_prefixes),
            }
        ),
    )

    async def invoke(name, arguments):
        require_write_path(tmp_path / "ambient.db")
        return ToolResult(success=True, data=arguments)

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({_NAME}),
        manifest=manifest,
        invoke=invoke,
        authorize=lambda scope: True,
        policy_revision="r",
        tools={},
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        denied = rpc(client, "tools/call", {"name": _NAME, "arguments": {"match": "A"}})
        assert denied["isError"]
        assert "write authority missing" in denied["content"][0]["text"]


def test_backend_write_authority_is_shared_by_direct_and_facade(tmp_path):
    from axm import require_write_path
    from axm.tools.write_scope import WriteContract

    target = tmp_path / "owned.txt"

    class Persist:
        name = "fixture_persist"

        def execute(self, value: str = "", **kwargs: object) -> ToolResult:
            require_write_path(target)
            target.write_text(value)
            return ToolResult(success=True, data={"value": value})

    async def invoke(name, arguments):
        raise AssertionError("UI invoke must not execute a backend tool")

    def app(prefixes: list[str]) -> ASGIApp:
        return create_scoped_mcp_app(
            allowed_tools=frozenset({"fixture_persist"}),
            manifest=None,
            invoke=invoke,
            authorize=lambda scope: True,
            policy_revision="fixture",
            tools={"fixture_persist": Persist()},
            write_contract=WriteContract.from_mapping(
                {"execution_root": str(tmp_path), "allowed_prefixes": prefixes}
            ),
        )

    with TestClient(app([]), base_url="http://127.0.0.1:9427") as client:
        assert rpc(
            client,
            "tools/call",
            {"name": "fixture_persist", "arguments": {"value": "denied"}},
        )["isError"]
        assert rpc(
            client,
            "tools/call",
            {
                "name": "axm_call",
                "arguments": {
                    "name": "fixture_persist",
                    "arguments": {"value": "denied"},
                },
            },
        )["isError"]
        assert not target.exists()
    with TestClient(app(["owned.txt"]), base_url="http://127.0.0.1:9427") as client:
        assert not rpc(
            client,
            "tools/call",
            {"name": "fixture_persist", "arguments": {"value": "direct"}},
        )["isError"]
        assert target.read_text() == "direct"
        assert not rpc(
            client,
            "tools/call",
            {
                "name": "axm_call",
                "arguments": {
                    "name": "fixture_persist",
                    "arguments": {"value": "facade"},
                },
            },
        )["isError"]
        assert target.read_text() == "facade"


def test_unknown_scope_and_backend_without_host_contract_fail(manifest):
    async def invoke(name, arguments):
        raise AssertionError("never invoke")

    with pytest.raises(ValueError, match="unknown"):
        create_scoped_mcp_app(
            allowed_tools=frozenset({"secret"}),
            manifest=manifest,
            invoke=invoke,
            authorize=lambda scope: True,
            policy_revision="r",
            tools={},
        )
