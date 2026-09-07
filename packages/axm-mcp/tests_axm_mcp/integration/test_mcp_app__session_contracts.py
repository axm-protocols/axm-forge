"""Integration tests for request-header session contract isolation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
from starlette.requests import Request

from axm_mcp import mcp_app, wrapping
from axm_mcp.session_contracts import SessionContractRegistry, UnboundSessionError


def _contract_header(
    execution_root: Path,
    *,
    allowed_prefixes: tuple[Path, ...] = (),
) -> str:
    return json.dumps(
        {
            "execution_root": str(execution_root),
            "allowed_prefixes": [str(prefix) for prefix in allowed_prefixes],
        }
    )


def _request(
    session_id: str,
    *,
    contract_header: str | None,
) -> Request:
    headers = [(MCP_SESSION_ID_HEADER.encode(), session_id.encode())]
    if contract_header is not None:
        headers.append((b"x-axm-write-contract", contract_header.encode()))
    return Request({"type": "http", "headers": headers})


def _bind_request(
    session_id: str,
    execution_root: Path,
    *,
    allowed_prefixes: tuple[Path, ...] = (),
) -> None:
    request = _request(
        session_id,
        contract_header=_contract_header(
            execution_root,
            allowed_prefixes=allowed_prefixes,
        ),
    )
    mcp_app.bind_session_from_headers(request.headers)


@pytest.fixture
def shared_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> SessionContractRegistry:
    registry = SessionContractRegistry(clock=lambda: 0.0)
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    return registry


@pytest.mark.integration
def test_two_header_bound_sessions_resolve_their_own_contracts(
    tmp_path: Path,
    shared_registry: SessionContractRegistry,
) -> None:
    """AC4: distinct HTTP session headers retain distinct declared roots."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"

    _bind_request("sess-a", root_a)
    _bind_request("sess-b", root_b)

    assert mcp_app.contract_for_session_id("sess-a").execution_root == str(root_a)
    assert mcp_app.contract_for_session_id("sess-b").execution_root == str(root_b)


@pytest.mark.integration
def test_cross_session_write_is_refused_with_requesting_identity(
    tmp_path: Path,
    shared_registry: SessionContractRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: session A cannot write inside only session B's prefixes."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    target = root_b / "src" / "x.py"
    _bind_request(
        "sess-a",
        root_a,
        allowed_prefixes=(root_a / "sess-a",),
    )
    _bind_request("sess-b", root_b, allowed_prefixes=(root_b,))
    monkeypatch.setattr(mcp_app, "current_session_id", lambda: "sess-a")
    context = SimpleNamespace(
        name="batch_edit",
        should_trace=False,
        write_contract_resolver=mcp_app._resolve_session_contract,
        shared_mode=True,
    )

    refusal = wrapping._write_refusal(
        context,
        {
            "path": str(root_b),
            "operations": [
                {"op": "create", "file": "src/x.py", "content": "forbidden"}
            ],
        },
    )

    assert refusal is not None
    assert refusal["success"] is False
    assert "sess-a" in str(refusal["error"])
    assert not target.exists()


@pytest.mark.integration
def test_session_without_contract_header_is_unbound(
    shared_registry: SessionContractRegistry,
) -> None:
    """AC2: a header identity without a scope is refused by identity."""
    request = _request("sess-c", contract_header=None)

    mcp_app.bind_session_from_headers(request.headers)

    with pytest.raises(UnboundSessionError) as exc_info:
        mcp_app.contract_for_session_id("sess-c")
    assert "sess-c" in str(exc_info.value)
