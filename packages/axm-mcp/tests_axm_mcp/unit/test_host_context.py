"""Transport identity is target-bound and never leaks across calls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from axm.tools.host_call_context import current_host_call

from axm_mcp.host_context import transport_host_call


def _context(token: str = "") -> object:
    return SimpleNamespace(
        request_context=SimpleNamespace(
            meta={
                "threadId": "thread-secret",
                "codex_bridge_mcp_call_id": "call-secret",
                "x-codex-turn-metadata": {"turn_id": "turn-secret"},
            },
            request=SimpleNamespace(
                headers={
                    "x-axm-host-token": token,
                }
            ),
        )
    )


def test_direct_and_facade_bind_only_the_effective_target() -> None:
    for name, arguments in (("agent_spawn", {}), ("axm_call", {"name": "agent_spawn"})):
        with transport_host_call(name, arguments, _context()):
            evidence = current_host_call("agent_spawn")
            assert evidence is not None
            assert evidence.thread_id == "thread-secret"
            assert evidence.turn_id == "turn-secret"
            assert evidence.call_id == "call-secret"
            assert current_host_call("agent_result") is None
            assert "secret" not in repr(evidence)
        assert current_host_call("agent_spawn") is None


def test_unrelated_call_does_not_gain_host_context() -> None:
    with transport_host_call("axm_call", {"name": "vault_get"}, _context()):
        assert current_host_call("agent_spawn") is None


def test_concurrent_contexts_and_exception_reset() -> None:
    async def run(token: str) -> str:
        with transport_host_call("agent_spawn", {}, _context(token)):
            await asyncio.sleep(0)
            evidence = current_host_call("agent_spawn")
            assert evidence is not None
            return evidence.client_token

    async def exercise() -> None:
        assert list(await asyncio.gather(run("a"), run("b"))) == ["a", "b"]
        try:
            with transport_host_call("agent_spawn", {}, _context()):
                raise ValueError("stop")
        except ValueError:
            pass
        assert current_host_call("agent_spawn") is None

    asyncio.run(exercise())


def test_surface_server_propagates_context_to_registered_tool() -> None:
    from axm_mcp.tool_surface import ToolSurfaceServer

    server = ToolSurfaceServer("probe")

    @server.tool(name="agent_context")
    def probe() -> str:
        evidence = current_host_call("agent_context")
        assert evidence is not None
        return evidence.thread_type

    async def exercise() -> None:
        result = await server.call_tool("agent_context", {}, _context())
        assert result.content[0].text == "str"
        assert current_host_call("agent_context") is None

    asyncio.run(exercise())


def test_turn_evidence_rejects_conflicts_and_malformed_values() -> None:
    from axm_mcp.host_context import _turn_id

    key = "x-codex-turn-metadata"
    assert _turn_id({key: {"turn_id": "t"}}, {}) == "t"
    assert _turn_id({}, {key: '{"turn_id":"t"}'}) == "t"
    assert _turn_id({key: {"turn_id": "t"}}, {key: '{"turn_id":"t"}'}) == "t"
    assert _turn_id({key: {"turn_id": "t"}}, {key: '{"turn_id":"other"}'}) is None
    assert _turn_id({key: "invalid"}, {key: '{"turn_id":"t"}'}) is None
    assert _turn_id({key: {"turn_id": "t"}}, {key: "invalid"}) is None
    assert _turn_id({}, {key: '{"turn_id":null}'}) is None


def test_missing_metadata_never_fabricates_identity() -> None:
    with transport_host_call("agent_context", {}, None):
        evidence = current_host_call("agent_context")
        assert evidence is not None
        assert not evidence.thread_id and not evidence.turn_id and not evidence.call_id
        assert (
            evidence.thread_type == evidence.turn_type == evidence.call_type == "absent"
        )
