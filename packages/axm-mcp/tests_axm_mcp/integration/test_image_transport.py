"""Real MCP HTTP responses preserve images through every dispatch route."""

import base64
from pathlib import Path
from typing import cast

import pytest
from axm import AXMTool, ToolImage, ToolResult
from axm.tools.write_scope import WriteContract
from mcp.server.mcpserver import MCPServer
from starlette.testclient import TestClient

from axm_mcp.discovery import ToolEntry, register_one
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade
from axm_mcp.scoped import create_scoped_mcp_app

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lS8AAAAASUVORK5CYII="
)


class PictureTool:
    """Emit a bounded immutable image with document provenance."""

    name = "picture"

    def execute(self) -> ToolResult:
        return ToolResult(
            success=True, text="revision abc; page 1", images=(ToolImage(PNG),)
        )


async def unused_ui(name: str, arguments: dict[str, object]) -> ToolResult:
    raise AssertionError("No UI dispatch expected")


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("facade", [False, True])
def test_http_image_transport(scoped: bool, facade: bool, tmp_path: Path) -> None:
    if scoped:
        app = create_scoped_mcp_app(
            allowed_tools=frozenset({"picture"}),
            manifest=None,
            invoke=unused_ui,
            authorize=lambda scope: True,
            policy_revision="image-transport",
            tools={"picture": cast(AXMTool, PictureTool())},
            write_contract=WriteContract.from_mapping(
                {"execution_root": str(tmp_path)}
            ),
        )
    else:
        server = MCPServer("image-transport")
        register_one(server, "picture", PictureTool())
        register_facade(
            server, ToolCatalog({"picture": cast(ToolEntry, PictureTool())})
        )
        app = server.streamable_http_app(stateless_http=True, json_response=True)
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
                    "name": "axm_call" if facade else "picture",
                    "arguments": {"name": "picture", "arguments": {}} if facade else {},
                },
            },
        )
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result.get("isError", False)
    assert result["content"] == [
        {"type": "text", "text": "revision abc; page 1"},
        {
            "type": "image",
            "data": base64.b64encode(PNG).decode("ascii"),
            "mimeType": "image/png",
        },
    ]
    assert not result.get("structuredContent")
