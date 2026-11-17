"""HTTP session binding for contracts declared during initialize."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from axm.tools.base import ToolResult
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

from axm_mcp import mcp_app
from axm_mcp.discovery import register_one
from axm_mcp.session_contracts import SessionContractRegistry

pytestmark = pytest.mark.integration


@pytest.fixture
def shared_http_app(monkeypatch: pytest.MonkeyPatch) -> object:
    """Serve an isolated MCP endpoint with a real write-scoped probe."""
    registry = SessionContractRegistry(clock=lambda: 0.0)
    monkeypatch.setattr(mcp_app, "session_contract_registry", registry)
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    server = type(mcp_app.mcp)("initialize-contract-test")
    monkeypatch.setattr(mcp_app, "mcp", server)

    class FilesystemWriter:
        def execute(self, *, path: str, file: str, content: str) -> ToolResult:
            Path(path, file).write_text(content, encoding="utf-8")
            return ToolResult(success=True, text="written")

    register_one(
        server,
        "write_file",
        FilesystemWriter(),
        registration=(
            True,
            lambda: mcp_app.contract_for_session_id(mcp_app.current_session_id()),
        ),
    )
    return mcp_app.build_http_app()


async def _initialize(client: httpx.AsyncClient, root: Path) -> str:
    response = await client.post(
        "/mcp",
        headers={
            "X-AXM-Write-Contract": json.dumps(
                {
                    "execution_root": str(root),
                    "allowed_prefixes": [str(root / "allowed")],
                    "markdown_only_prefixes": [],
                }
            ),
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "1.0"},
            },
        },
    )
    assert response.status_code == 200, response.text
    session_id = response.headers.get(MCP_SESSION_ID_HEADER)
    assert isinstance(session_id, str) and session_id
    return session_id


@pytest.mark.asyncio
async def test_initialize_contract_is_bound_to_response_session(
    tmp_path: Path,
    shared_http_app: object,
) -> None:
    """AC1: initialize alone binds its scope to the returned session id."""
    transport = httpx.ASGITransport(app=shared_http_app)
    async with shared_http_app.router.lifespan_context(shared_http_app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            session_id = await _initialize(client, tmp_path)
            contract = mcp_app.contract_for_session_id(session_id)
            assert str(tmp_path / "allowed") in contract.allowed_prefixes


@pytest.mark.asyncio
async def test_initialize_only_contract_blocks_forbidden_but_allows_write(
    tmp_path: Path,
    shared_http_app: object,
) -> None:
    """AC2: header-less calls reject a forbidden write and perform an allowed one."""
    allowed = tmp_path / "allowed"
    forbidden = tmp_path / "forbidden"
    allowed.mkdir()
    forbidden.mkdir()
    transport = httpx.ASGITransport(app=shared_http_app)
    async with shared_http_app.router.lifespan_context(shared_http_app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            session_id = await _initialize(client, tmp_path)
            headers = {
                MCP_SESSION_ID_HEADER: session_id,
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            }
            initialized = await client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            assert initialized.status_code == 202
            for request_id, directory in enumerate((forbidden, allowed), start=2):
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {
                                "path": str(directory),
                                "file": "x.txt",
                                "content": "written",
                            },
                        },
                    },
                )
                assert response.status_code == 200
    assert not (forbidden / "x.txt").exists()
    assert (allowed / "x.txt").read_text(encoding="utf-8") == "written"


async def test_v2_transport_keeps_restrictions_after_session_binding(
    tmp_path: Path, shared_http_app: object
) -> None:
    from axm.tools.contract_wire import contract_to_wire
    from axm.tools.write_scope import WriteContract, restrict_write_contract

    child = tmp_path / "child"
    child.mkdir()
    broad = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [str(tmp_path)],
            "read_roots": [str(tmp_path)],
        }
    )
    narrow = WriteContract.from_mapping(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [str(child)],
            "read_roots": [str(child)],
        }
    )
    combined = restrict_write_contract(broad, (narrow,))
    assert combined is not None
    wire = contract_to_wire(combined)
    transport = httpx.ASGITransport(app=shared_http_app)
    async with shared_http_app.router.lifespan_context(shared_http_app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            probe = await client.options(
                "/mcp", headers={"x-axm-write-contract-probe": "2"}
            )
            assert probe.status_code == 200
            assert probe.headers["x-axm-write-contract-version"] == "2"
            assert probe.headers["x-axm-tool-surface-version"] == "1"
            headers = {
                "x-axm-write-contract": wire,
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            }
            init = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "v2-test", "version": "1"},
                    },
                },
            )
            assert init.status_code == 200, init.text
            headers.pop("x-axm-write-contract")
            headers[MCP_SESSION_ID_HEADER] = init.headers[MCP_SESSION_ID_HEADER]
            await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            for request_id, target in enumerate((tmp_path, child), start=2):
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "tools/call",
                        "params": {
                            "name": "write_file",
                            "arguments": {
                                "path": str(target),
                                "file": "v2.txt",
                                "content": "ok",
                            },
                        },
                    },
                )
                assert response.status_code == 200
            bound = mcp_app.contract_for_session_id(headers[MCP_SESSION_ID_HEADER])
            assert not bound.readable(str(tmp_path / "outside.txt"))
            assert bound.readable(str(child / "inside.txt"))
    assert not (tmp_path / "v2.txt").exists()
    assert (child / "v2.txt").read_text() == "ok"


def test_v1_exact_files_preserved_and_old_decoder_rejects_v2(tmp_path: Path) -> None:
    from axm.tools.contract_wire import contract_to_wire
    from axm.tools.write_scope import WriteContract
    from pydantic import ValidationError

    from axm_mcp.session_contracts import (
        _WRITE_CONTRACT_ADAPTER,
        parse_write_contract_header,
    )

    target = tmp_path / "exact.txt"
    target.write_text("ok")
    legacy = json.dumps(
        {
            "execution_root": str(tmp_path),
            "allowed_prefixes": [],
            "markdown_only_prefixes": [],
            "read_files": [str(target)],
            "allowed_files": [str(target)],
        }
    )
    parsed = parse_write_contract_header(legacy)
    assert parsed.readable(str(target))
    assert parsed.permits(str(target))
    wire = contract_to_wire(WriteContract.from_json(legacy))
    with pytest.raises(ValidationError):
        _WRITE_CONTRACT_ADAPTER.validate_json(wire)


async def test_scoped_real_http_refuses_vault_and_facade_target(
    tmp_path: Path, shared_http_app: object
) -> None:
    keychain: list[str] = []

    @mcp_app.mcp.tool()
    def vault_delete() -> str:
        keychain.append("deleted")
        return "deleted"

    @mcp_app.mcp.tool()
    def axm_call(name: str) -> str:
        keychain.append(name)
        return name

    transport = httpx.ASGITransport(app=shared_http_app)
    async with shared_http_app.router.lifespan_context(shared_http_app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            probe = await client.options(
                "/mcp", headers={"x-axm-write-contract-probe": "2"}
            )
            assert probe.headers["x-axm-tool-surface-version"] == "1"
            headers = {
                "x-axm-tool-surface": json.dumps(["write_file", "axm_call"]),
                "x-axm-write-contract": json.dumps(
                    {
                        "execution_root": str(tmp_path),
                        "allowed_prefixes": [str(tmp_path)],
                        "markdown_only_prefixes": [],
                    }
                ),
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            }
            init = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "surface-test", "version": "1"},
                    },
                },
            )
            assert init.status_code == 200
            headers.pop("x-axm-tool-surface")
            headers.pop("x-axm-write-contract")
            headers[MCP_SESSION_ID_HEADER] = init.headers[MCP_SESSION_ID_HEADER]
            await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            for request_id, name, arguments in (
                (2, "vault_delete", {}),
                (3, "axm_call", {"name": "vault_delete"}),
            ):
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                )
                assert response.status_code == 200
                assert "undeclared tool refused" in response.text
            allowed = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "write_file",
                        "arguments": {
                            "path": str(tmp_path),
                            "file": "allowed.txt",
                            "content": "ok",
                        },
                    },
                },
            )
            assert allowed.status_code == 200
    assert keychain == []
    assert (tmp_path / "allowed.txt").read_text() == "ok"
