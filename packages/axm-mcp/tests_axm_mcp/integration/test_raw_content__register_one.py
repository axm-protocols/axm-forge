"""Raw text status survives real MCP HTTP dispatch."""

from __future__ import annotations

from typing import cast

import pytest
from axm import ToolResult
from mcp.server.mcpserver import MCPServer
from starlette.testclient import TestClient

from axm_mcp.discovery import ToolEntry, register_one
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade


class RawResult(ToolResult):
    mcp_raw_content = True


class TextTool:
    def execute(self, fail: bool = False, raw: bool = True) -> ToolResult:
        result_type = RawResult if raw else ToolResult
        return result_type(
            success=not fail, error="failed" if fail else None, text="compact"
        )


@pytest.mark.integration
@pytest.mark.parametrize("facade", [False, True])
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("raw", [False, True])
def test_http_raw_content_status(facade: bool, fail: bool, raw: bool) -> None:
    server = MCPServer("raw-content")
    tool = TextTool()
    register_one(server, "text_tool", tool)
    register_facade(server, ToolCatalog({"text_tool": cast(ToolEntry, tool)}))
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    args = {"fail": fail, "raw": raw}
    with TestClient(app, base_url="http://127.0.0.1:9427") as client:
        response = client.post(
            "/mcp",
            headers={
                "accept": "application/json, text/event-stream",
                "mcp-protocol-version": "2025-06-18",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "axm_call" if facade else "text_tool",
                    "arguments": {"name": "text_tool", "arguments": args}
                    if facade
                    else args,
                },
            },
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result.get("isError", False) is (fail and raw)
    assert "structuredContent" not in result
    assert result["content"] == [
        {"type": "text", "text": "✗ failed\ncompact" if fail else "compact"}
    ]
