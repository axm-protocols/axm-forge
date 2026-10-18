"""A multimodal result retains image bytes across every model-facing route."""

from __future__ import annotations

import base64
from typing import cast
from unittest.mock import patch

import pytest
from axm import ToolImage, ToolResult
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent

from axm_mcp.discovery import ToolEntry, register_tools
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade
from axm_mcp.images import image_result
from axm_mcp.scoped import _backend_result
from axm_mcp.wrapping import build_wrappers

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lS8AAAAASUVORK5CYII="
)


class PictureTool:
    """A read-only tool whose result contains a real PNG and concise provenance."""

    name = "picture"

    def execute(self, *, fail: bool = False) -> ToolResult:
        return ToolResult(
            success=not fail,
            data={"large_unused_payload": "never sent"},
            text="revision abc; page 1",
            error="refused" if fail else None,
            images=(ToolImage(PNG),),
        )


def assert_picture(result: object) -> None:
    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    assert result.structured_content is None
    assert len(result.content) == 2
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "revision abc; page 1"
    picture = result.content[1]
    assert isinstance(picture, ImageContent)
    assert picture.mime_type == "image/png"
    assert base64.b64decode(picture.data) == PNG


def test_direct_and_scoped_wrappers_keep_images_and_trace_only_provenance() -> None:
    for scoped in (False, True):
        wrapper, _ = build_wrappers("picture", PictureTool(), text_status=scoped)
        with patch("axm_mcp.wrapping.log_external_step") as trace:
            rendered = wrapper()
        assert_picture(rendered)
        assert_picture(_backend_result(rendered, tool_result=True))
        assert "iVBOR" not in repr(trace.call_args)
        assert "never sent" not in repr(trace.call_args)


@pytest.mark.asyncio
async def test_facade_sync_async_and_registered_mcp_keep_image_blocks() -> None:
    catalog = ToolCatalog({"picture": cast(ToolEntry, PictureTool())})
    assert_picture(catalog.call("picture"))
    assert_picture(await catalog.acall("picture"))
    server = MCPServer("pictures")
    register_facade(server, catalog)
    register_tools(server, {"picture": cast(ToolEntry, PictureTool())})
    assert_picture(await server.call_tool("axm_call", {"name": "picture"}))
    assert_picture(await server.call_tool("picture", {}))


def test_failed_tools_never_attach_their_image() -> None:
    wrapper, _ = build_wrappers("picture", PictureTool())
    result = wrapper(fail=True)
    assert isinstance(result, str)
    assert "refused" in result
    assert "iVBOR" not in result


def test_transport_refuses_untyped_image_payloads() -> None:
    with pytest.raises(ValueError, match="ToolImage"):
        image_result(({"path": "/private/data.png"},), "not authorized")
