from __future__ import annotations

import importlib
import json
from types import ModuleType

import pytest
from axm.tools.write_scope import WriteContract


def _session_contracts() -> ModuleType:
    return importlib.import_module("axm_mcp.session_contracts")


def _contract(execution_root: str) -> WriteContract:
    return WriteContract.from_json(
        json.dumps(
            {
                "execution_root": execution_root,
                "allowed_prefixes": [execution_root],
                "markdown_only_prefixes": [],
            }
        )
    )


def test_two_sessions_resolve_their_own_contract() -> None:
    """AC1: bindings in one registry remain isolated by session id."""
    session_contracts = _session_contracts()
    now = 100.0
    registry = session_contracts.SessionContractRegistry(clock=lambda: now)
    contract_a = _contract("/workspace/a")
    contract_b = _contract("/workspace/b")

    registry.bind("s-a", contract_a)
    registry.bind("s-b", contract_b)

    assert registry.resolve("s-a") is contract_a
    assert registry.resolve("s-b") is contract_b


def test_resolve_unbound_session_raises_and_names_session() -> None:
    """AC2: resolving an unbound session raises an error naming its id."""
    session_contracts = _session_contracts()
    registry = session_contracts.SessionContractRegistry(clock=lambda: 100.0)

    with pytest.raises(session_contracts.UnboundSessionError) as exc_info:
        registry.resolve("s-ghost")

    assert "s-ghost" in str(exc_info.value)


def test_release_removes_session_binding() -> None:
    """AC3: release prevents reuse of a closed session identity."""
    session_contracts = _session_contracts()
    registry = session_contracts.SessionContractRegistry(clock=lambda: 100.0)
    registry.bind("s-a", _contract("/workspace/a"))

    registry.release("s-a")
    registry.release("s-a")

    with pytest.raises(session_contracts.UnboundSessionError):
        registry.resolve("s-a")


def test_purge_expired_evicts_old_and_keeps_fresh_binding() -> None:
    """AC4: TTL purge evicts old bindings while preserving fresh ones."""
    session_contracts = _session_contracts()
    current_time = [1_000.0]
    registry = session_contracts.SessionContractRegistry(
        clock=lambda: current_time[0],
        ttl_seconds=60,
    )
    contract_a = _contract("/workspace/a")
    contract_b = _contract("/workspace/b")
    registry.bind("s-old", contract_a)
    current_time[0] += 30
    registry.bind("s-new", contract_b)

    registry.purge_expired(1_061.0)

    with pytest.raises(session_contracts.UnboundSessionError):
        registry.resolve("s-old")
    assert registry.resolve("s-new") is contract_b


def test_parse_write_contract_header_binds_exact_decoded_contract() -> None:
    """AC1: the three header fields survive decoding and registry binding."""
    session_contracts = _session_contracts()
    raw = json.dumps(
        {
            "execution_root": "/tmp/root",
            "allowed_prefixes": ["/tmp/root/src"],
            "markdown_only_prefixes": ["/tmp/root/docs"],
        }
    )

    contract = session_contracts.parse_write_contract_header(raw)
    registry = session_contracts.SessionContractRegistry(clock=lambda: 100.0)
    registry.bind("s1", contract)

    assert contract.execution_root == "/tmp/root"
    assert contract.allowed_prefixes == ["/tmp/root/src"]
    assert contract.markdown_only_prefixes == ["/tmp/root/docs"]
    assert registry.resolve("s1") is contract


def test_parse_write_contract_header_rejects_non_json_payload() -> None:
    """AC2: invalid JSON raises the typed error naming the HTTP header."""
    session_contracts = _session_contracts()

    with pytest.raises(session_contracts.WriteContractHeaderError) as exc_info:
        session_contracts.parse_write_contract_header("not-json")

    assert "X-AXM-Write-Contract" in str(exc_info.value)


def test_parse_write_contract_header_rejects_missing_execution_root() -> None:
    """AC3: a missing execution_root raises without creating a binding."""
    session_contracts = _session_contracts()
    registry = session_contracts.SessionContractRegistry(clock=lambda: 100.0)
    raw = json.dumps(
        {
            "allowed_prefixes": ["/tmp/root/src"],
            "markdown_only_prefixes": [],
        }
    )

    with pytest.raises(session_contracts.WriteContractHeaderError) as exc_info:
        session_contracts.parse_write_contract_header(raw)

    assert "execution_root" in str(exc_info.value)
    with pytest.raises(session_contracts.UnboundSessionError):
        registry.resolve("s1")
