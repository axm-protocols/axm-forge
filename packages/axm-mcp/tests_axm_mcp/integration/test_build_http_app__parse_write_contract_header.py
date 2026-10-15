"""HTTP write-contract rejection at the served ASGI boundary."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from axm_mcp import mcp_app


@pytest.fixture
def served_app(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], object]:
    """Serve the real AXM HTTP wrapper around a recording MCP transport."""
    dispatched: list[str] = []

    async def endpoint(request: Request) -> JSONResponse:
        payload = await request.json()
        method = payload["method"]
        dispatched.append(method)
        if method == "tools/call":
            arguments = payload["params"]["arguments"]
            destination = Path(arguments["path"]) / arguments["file"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(arguments["content"])
        return JSONResponse(
            {"jsonrpc": "2.0", "id": payload["id"], "result": {}},
            headers={MCP_SESSION_ID_HEADER: "session-1"},
        )

    monkeypatch.setattr(
        MCPServer,
        "streamable_http_app",
        lambda self, **kwargs: Starlette(
            routes=[Route("/mcp", endpoint, methods=["POST"])]
        ),
    )
    return dispatched, mcp_app


def _contract(root: Path) -> str:
    return json.dumps(
        {
            "execution_root": str(root),
            "allowed_prefixes": [str(root)],
            "markdown_only_prefixes": [],
        }
    )


def _request(method: str, *, path: Path | None = None) -> dict[str, object]:
    params: dict[str, object] = {}
    if path is not None:
        params = {
            "name": "write_file",
            "arguments": {
                "path": str(path.parent),
                "file": path.name,
                "content": "written",
            },
        }
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


async def _post(
    app: object,
    method: str,
    *,
    header: str | None,
    session: bool,
    path: Path | None = None,
) -> httpx.Response:
    headers = {"accept": "application/json, text/event-stream"}
    if header is not None:
        headers["X-AXM-Write-Contract"] = header
    if session:
        headers[MCP_SESSION_ID_HEADER] = "session-1"
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.post(
            "/mcp", headers=headers, json=_request(method, path=path)
        )


@pytest.mark.integration
def test_shared_rejects_malformed_initialize_header(
    monkeypatch: pytest.MonkeyPatch, served_app: tuple[list[str], object]
) -> None:
    """AC1: malformed initialize contracts receive 400 before MCP dispatch."""
    dispatched, _ = served_app
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    monkeypatch.setattr(mcp_app, "resolve_serve_mode", lambda explicit=None: "shared")
    app = mcp_app.build_http_app()

    response = asyncio.run(_post(app, "initialize", header="{not json", session=False))

    assert response.status_code == 400
    assert (
        "write contract" in response.text.lower()
        or "write-contract" in response.text.lower()
    )
    assert MCP_SESSION_ID_HEADER.lower() not in response.headers
    assert dispatched == []


@pytest.mark.integration
def test_shared_rejects_invalid_schema_on_session_write(
    monkeypatch: pytest.MonkeyPatch,
    served_app: tuple[list[str], object],
    tmp_path: Path,
) -> None:
    """AC1: schema errors on a session tool call receive 400 and write nothing."""
    dispatched, _ = served_app
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    monkeypatch.setattr(mcp_app, "resolve_serve_mode", lambda explicit=None: "shared")
    app = mcp_app.build_http_app()
    destination = tmp_path / "allowed" / "x.txt"

    async def requests() -> tuple[httpx.Response, httpx.Response]:
        opened = await _post(
            app, "initialize", header=_contract(tmp_path / "allowed"), session=False
        )
        rejected = await _post(
            app,
            "tools/call",
            header='{"execution_root": 1}',
            session=True,
            path=destination,
        )
        return opened, rejected

    opened, rejected = asyncio.run(requests())

    assert opened.status_code == 200
    assert rejected.status_code == 400
    assert (
        "write contract" in rejected.text.lower()
        or "write-contract" in rejected.text.lower()
    )
    assert not destination.exists()
    assert dispatched == ["initialize"]


@pytest.mark.integration
def test_dedicated_rejects_contract_and_keeps_headerless_write(
    monkeypatch: pytest.MonkeyPatch,
    served_app: tuple[list[str], object],
    tmp_path: Path,
) -> None:
    """AC2: dedicated mode rejects headers before dispatch and permits local writes."""
    dispatched, _ = served_app
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", False)
    monkeypatch.setattr(
        mcp_app, "resolve_serve_mode", lambda explicit=None: "dedicated"
    )
    app = mcp_app.build_http_app()
    contract = _contract(tmp_path / "allowed")
    forbidden = tmp_path / "forbidden" / "x.txt"
    free = tmp_path / "free" / "x.txt"

    async def requests() -> tuple[
        httpx.Response, httpx.Response, httpx.Response, httpx.Response
    ]:
        rejected_init = await _post(app, "initialize", header=contract, session=False)
        rejected_write = await _post(
            app, "tools/call", header=contract, session=True, path=forbidden
        )
        opened = await _post(app, "initialize", header=None, session=False)
        wrote = await _post(app, "tools/call", header=None, session=True, path=free)
        return rejected_init, rejected_write, opened, wrote

    rejected_init, rejected_write, opened, wrote = asyncio.run(requests())

    assert rejected_init.status_code == 403
    assert rejected_write.status_code == 403
    assert "dedicated" in rejected_init.text.lower()
    assert "dedicated" in rejected_write.text.lower()
    assert not forbidden.exists()
    assert opened.status_code == 200
    assert wrote.status_code == 200
    assert free.read_text() == "written"
    assert dispatched == ["initialize", "tools/call"]


@pytest.mark.integration
def test_rejections_emit_one_warning_per_request(
    monkeypatch: pytest.MonkeyPatch,
    served_app: tuple[list[str], object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC3: each rejection logs its reason once at WARNING level."""
    dispatched, _ = served_app
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", True)
    monkeypatch.setattr(mcp_app, "resolve_serve_mode", lambda explicit=None: "shared")
    shared = mcp_app.build_http_app()
    monkeypatch.setattr(mcp_app, "_SHARED_MODE", False)
    monkeypatch.setattr(
        mcp_app, "resolve_serve_mode", lambda explicit=None: "dedicated"
    )
    dedicated = mcp_app.build_http_app()

    async def requests() -> tuple[httpx.Response, httpx.Response]:
        invalid = await _post(shared, "initialize", header="{not json", session=False)
        refused = await _post(dedicated, "initialize", header="{}", session=False)
        return invalid, refused

    with caplog.at_level(logging.WARNING, logger="axm_mcp.mcp_app"):
        invalid, refused = asyncio.run(requests())

    records = [
        record
        for record in caplog.records
        if record.name == "axm_mcp.mcp_app" and record.levelno == logging.WARNING
    ]
    assert invalid.status_code == 400
    assert refused.status_code == 403
    assert len(records) == 2
    assert (
        "write contract" in records[0].message.lower()
        or "write-contract" in records[0].message.lower()
    )
    assert "dedicated" in records[1].message.lower()
    assert dispatched == []
