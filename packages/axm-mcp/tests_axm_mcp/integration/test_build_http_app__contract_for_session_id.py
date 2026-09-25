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
