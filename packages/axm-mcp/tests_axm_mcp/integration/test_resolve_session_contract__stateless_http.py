from __future__ import annotations

import json

import httpx
import pytest

from axm_mcp.mcp_app import _resolve_session_contract, _SessionContractMiddleware

pytestmark = pytest.mark.integration


async def test_declared_contract_is_available_without_mcp_session_id(tmp_path):
    root = str(tmp_path)
    observed = []

    async def tool_app(scope, receive, send):
        contract = _resolve_session_contract()
        observed.append(contract.execution_root)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = _SessionContractMiddleware(tool_app, mode="shared")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            headers={
                "X-AXM-Write-Contract": json.dumps(
                    {
                        "execution_root": root,
                        "read_roots": [root],
                        "allowed_prefixes": [],
                        "markdown_only_prefixes": [],
                    }
                ),
            },
        )
    assert response.status_code == 200
    assert observed == [root]
    with pytest.raises(RuntimeError, match="no current MCP session identity"):
        _resolve_session_contract()
