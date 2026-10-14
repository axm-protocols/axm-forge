"""Independent adversarial review of revocation and nested authority."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from axm import AXMTool, ToolResult, require_write_path
from axm.tools import load_tool, override_tools, tool_node
from axm.tools.write_scope import WriteContract
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from axm_mcp import create_scoped_mcp_app

pytestmark = pytest.mark.integration
_HEADERS = {
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-06-18",
}


async def _unused(name, arguments):
    raise AssertionError("No UI invocation in backend security probes")


@pytest.mark.parametrize("facade", [False, True])
def test_failed_tool_with_text_remains_structurally_failed(tmp_path, facade):
    class Refusal:
        name = "fixture_refusal"

        def execute(self) -> ToolResult:
            return ToolResult(success=False, error="denied", text="Diagnostic evidence")

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_refusal"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="review",
        tools={"fixture_refusal": cast(AXMTool, Refusal())},
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        result = (
            _rpc(client, "axm_call", {"name": "fixture_refusal"})
            if facade
            else _rpc(client, "fixture_refusal", {})
        )
    assert "denied" in result["content"][0]["text"]
    assert result["isError"], "failed ToolResult was presented as a successful MCP call"


def _rpc(client, name, arguments) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        headers=_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json()["result"])


@pytest.mark.parametrize("facade", [False, True])
def test_nested_load_cannot_bypass_host_write_authority(tmp_path, facade):
    from axm_edit.tools.batch_edit import BatchEditTool

    root = tmp_path / "owned"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    args = {
        "path": str(tmp_path),
        "operations": [{"op": "create", "file": "outside.txt", "content": "forbidden"}],
        "lint": False,
    }

    class Proxy:
        name = "fixture_proxy"

        def execute(self) -> ToolResult:
            return load_tool("batch_edit").execute(**args)

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_proxy", "batch_edit"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="review",
        tools={"fixture_proxy": cast(AXMTool, Proxy()), "batch_edit": BatchEditTool()},
        write_contract=WriteContract.from_mapping(
            {"execution_root": str(root), "allowed_prefixes": [str(root)]}
        ),
    )
    with override_tools({"batch_edit": BatchEditTool()}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            direct = _rpc(client, "batch_edit", args)
            assert direct["isError"]
            assert not outside.exists()
            result = (
                _rpc(client, "axm_call", {"name": "fixture_proxy"})
                if facade
                else _rpc(client, "fixture_proxy", {})
            )
    assert not outside.exists(), (
        "nested load executed the same forbidden filesystem write"
    )
    assert result["isError"]


def test_revoked_scope_cannot_dispatch_an_allowed_cached_nested_node(tmp_path):
    state = {"authorized": True, "nested": 0}

    class Nested:
        name = "fixture_nested"

        def execute(self) -> ToolResult:
            state["nested"] += 1
            return ToolResult(success=True, data={"value": "ran"})

    cached = tool_node("fixture_nested", returns={"value": "value"})

    class Proxy:
        name = "fixture_proxy"

        def execute(self) -> ToolResult:
            state["authorized"] = False
            return ToolResult(success=True, data=cached({}))

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_proxy", "fixture_nested"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: bool(state["authorized"]),
        policy_revision="review",
        tools={
            "fixture_proxy": cast(AXMTool, Proxy()),
            "fixture_nested": cast(AXMTool, Nested()),
        },
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with override_tools({"fixture_nested": cast(AXMTool, Nested())}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            result = _rpc(client, "fixture_proxy", {})
    assert state["nested"] == 0, "authorization revoked before the nested dispatch"
    assert result["isError"]


@pytest.mark.asyncio
async def test_waiting_backend_dispatch_revalidates_revocation(tmp_path, monkeypatch):
    from axm_mcp import wrapping

    monkeypatch.setattr(wrapping, "_HTTP_MODE", True)
    first_started = threading.Event()
    release = threading.Event()
    second_authorized = asyncio.Event()
    executed = []
    authorized = {"value": True, "checks": 0}

    class Locked:
        name = "git_review"

        def execute(self, path: str, label: str) -> ToolResult:
            executed.append(label)
            if label == "first":
                first_started.set()
                assert release.wait(5), "probe cleanup did not release first call"
            return ToolResult(success=True, data={"label": label})

    def authorize(scope):
        authorized["checks"] += 1
        if authorized["checks"] >= 4:
            second_authorized.set()
        return authorized["value"]

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"git_review"}),
        manifest=None,
        invoke=_unused,
        authorize=authorize,
        policy_revision="review",
        tools={"git_review": cast(AXMTool, Locked())},
        write_contract=WriteContract.from_mapping(
            {"execution_root": str(tmp_path), "allowed_prefixes": [str(tmp_path)]}
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:9427"
    ) as client:

        async def call(label) -> httpx.Response:
            return await client.post(
                "/mcp",
                headers=_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": label,
                    "method": "tools/call",
                    "params": {
                        "name": "git_review",
                        "arguments": {"path": str(tmp_path), "label": label},
                    },
                },
            )

        first = asyncio.create_task(call("first"))
        assert await asyncio.to_thread(first_started.wait, 5)
        second = asyncio.create_task(call("second"))
        try:
            await asyncio.wait_for(second_authorized.wait(), 5)
            await asyncio.sleep(0)
            assert executed == ["first"]
            authorized["value"] = False
        finally:
            release.set()
        responses = await asyncio.gather(first, second)
    assert executed == ["first"], (
        "queued backend operation ran after host revoked capability"
    )
    assert responses[1].json()["result"]["isError"]


@pytest.mark.parametrize("revoke_nested", [False, True])
def test_async_host_policy_revalidates_nested_execution_without_deadlock(
    tmp_path, revoke_nested
):
    live = {"authorized": True}
    effects = []
    nested = tool_node("fixture_nested", returns={"value": "value"})

    class Nested:
        name = "fixture_nested"

        def execute(self) -> ToolResult:
            effects.append("nested")
            return ToolResult(success=True, data={"value": "observed"})

    class Proxy:
        name = "fixture_proxy"

        def execute(self) -> ToolResult:
            if revoke_nested:
                live["authorized"] = False
            return ToolResult(success=True, data=nested({}))

    async def authorize(scope) -> bool:
        await asyncio.sleep(0)
        return live["authorized"]

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_proxy", "fixture_nested"}),
        manifest=None,
        invoke=_unused,
        authorize=authorize,
        policy_revision="async-review",
        tools={
            "fixture_proxy": cast(AXMTool, Proxy()),
            "fixture_nested": cast(AXMTool, Nested()),
        },
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with override_tools({"fixture_nested": cast(AXMTool, Nested())}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            result = _rpc(client, "fixture_proxy", {})
    assert result["isError"] is revoke_nested
    assert effects == ([] if revoke_nested else ["nested"])


def test_nested_authorized_write_uses_host_root_not_process_cwd(tmp_path):
    from axm_edit.tools.batch_edit import BatchEditTool

    owned = tmp_path / "owned"
    owned.mkdir()

    class Proxy:
        name = "fixture_proxy"

        def execute(self) -> ToolResult:
            return load_tool("batch_edit").execute(
                operations=[{"op": "create", "file": "allowed.txt", "content": "ok"}],
                lint=False,
            )

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_proxy", "batch_edit"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="root-review",
        tools={
            "fixture_proxy": cast(AXMTool, Proxy()),
            "batch_edit": BatchEditTool(),
        },
        write_contract=WriteContract.from_mapping(
            {
                "execution_root": str(owned),
                "allowed_prefixes": [str(owned)],
            }
        ),
    )
    with override_tools({"batch_edit": BatchEditTool()}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            result = _rpc(client, "fixture_proxy", {})
    assert not result["isError"]
    assert (owned / "allowed.txt").read_text() == "ok"
    assert not (tmp_path / "allowed.txt").exists()


def test_cached_scoped_handle_refuses_after_request_loop_has_closed(tmp_path):
    saved = []
    effects = []

    class Nested:
        name = "fixture_nested"

        def execute(self) -> ToolResult:
            effects.append("unexpected")
            return ToolResult(success=True)

    class Proxy:
        name = "fixture_proxy"

        def execute(self) -> ToolResult:
            saved.append(load_tool("fixture_nested"))
            return ToolResult(success=True)

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_proxy", "fixture_nested"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="closed-review",
        tools={
            "fixture_proxy": cast(AXMTool, Proxy()),
            "fixture_nested": cast(AXMTool, Nested()),
        },
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with override_tools({"fixture_nested": cast(AXMTool, Nested())}):
        with TestClient(app, base_url="http://127.0.0.1:9427") as client:
            assert not _rpc(client, "fixture_proxy", {})["isError"]
    with pytest.raises(PermissionError, match="scope unavailable"):
        saved[0].execute()
    assert effects == []


def test_failing_async_lease_check_never_executes_backend(tmp_path):
    checks = []
    effects = []

    class Tool:
        name = "fixture_backend"

        def execute(self) -> ToolResult:
            effects.append("unexpected")
            return ToolResult(success=True)

    async def authorize(scope) -> bool:
        checks.append(scope["path"])
        if len(checks) >= 3:
            raise RuntimeError("lease service unavailable")
        return True

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_backend"}),
        manifest=None,
        invoke=_unused,
        authorize=authorize,
        policy_revision="failed-lease-review",
        tools={"fixture_backend": cast(AXMTool, Tool())},
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        result = _rpc(client, "fixture_backend", {})
    assert result["isError"]
    assert "lease service unavailable" in result["content"][0]["text"]
    assert effects == []


@pytest.mark.parametrize("facade", [False, True])
@pytest.mark.parametrize("value", ["false", 1, [False], None])
def test_malformed_success_is_structurally_failed_through_both_routes(
    tmp_path, facade, value
):
    class Tool:
        name = "fixture_broken"

        def execute(self):
            return SimpleNamespace(
                success=value, data={}, text="provider refused", error="denied"
            )

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_broken"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="strict-bool",
        tools={"fixture_broken": cast(AXMTool, Tool())},
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        result = (
            _rpc(client, "axm_call", {"name": "fixture_broken"})
            if facade
            else _rpc(client, "fixture_broken", {})
        )
    assert result["isError"]
    assert result["structuredContent"]["success"] is False
    assert "malformed ToolResult" in result["content"][0]["text"]


@pytest.mark.parametrize(
    ("origin_write", "current_write", "allowed"),
    [(False, True, False), (True, False, False), (True, True, True)],
)
def test_retained_service_handle_intersects_both_live_body_authorities(
    tmp_path, origin_write, current_write, allowed
):
    root_a, root_b = tmp_path / "a", tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    target = tmp_path / "configured.txt"
    saved = []

    class Persist:
        name = "fixture_persist"

        def execute(self) -> ToolResult:
            require_write_path(target)
            target.write_text("authorized by both")
            return ToolResult(success=True)

    class Retain:
        name = "fixture_retain"

        def execute(self) -> ToolResult:
            saved.append(load_tool("fixture_persist"))
            return ToolResult(success=True)

    class Invoke:
        name = "fixture_invoke"

        def execute(self) -> ToolResult:
            return saved[0].execute()

    def app(root, tools, writable) -> ASGIApp:
        return create_scoped_mcp_app(
            allowed_tools=frozenset(tools),
            manifest=None,
            invoke=_unused,
            authorize=lambda scope: True,
            policy_revision=str(root),
            tools=tools,
            write_contract=WriteContract.from_mapping(
                {
                    "execution_root": str(root),
                    "read_roots": [str(target)],
                    "allowed_prefixes": [str(target)] if writable else [],
                }
            ),
        )

    persist = cast(AXMTool, Persist())
    with override_tools({"fixture_persist": persist}):
        with TestClient(
            app(
                root_a,
                {"fixture_retain": cast(AXMTool, Retain()), "fixture_persist": persist},
                origin_write,
            ),
            base_url="http://127.0.0.1:9427",
        ) as client_a:
            assert not _rpc(client_a, "fixture_retain", {})["isError"]
            with TestClient(
                app(
                    root_b,
                    {
                        "fixture_invoke": cast(AXMTool, Invoke()),
                        "fixture_persist": persist,
                    },
                    current_write,
                ),
                base_url="http://127.0.0.1:9427",
            ) as client_b:
                result = _rpc(client_b, "fixture_invoke", {})
    assert result["isError"] is (not allowed)
    assert target.exists() is allowed


@pytest.mark.parametrize(
    ("payload", "failed"),
    [
        ("bare text without envelope", True),
        ({"success": 1}, True),
        ({"value": "missing success"}, True),
        ({"success": True, "value": "valid"}, False),
    ],
)
def test_plain_backend_result_requires_a_boolean_structural_envelope(
    tmp_path, payload, failed
):
    def backend(**kwargs):
        return payload

    app = create_scoped_mcp_app(
        allowed_tools=frozenset({"fixture_plain"}),
        manifest=None,
        invoke=_unused,
        authorize=lambda scope: True,
        policy_revision="plain-envelope",
        tools={"fixture_plain": cast(AXMTool, backend)},
        write_contract=WriteContract.from_mapping({"execution_root": str(tmp_path)}),
    )
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        result = _rpc(client, "fixture_plain", {})
    assert result["isError"] is failed
