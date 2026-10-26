"""A bad image cannot become a false argument error or enter a conversation."""

import io
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from axm import ToolImage, ToolResult
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent
from PIL import Image

from axm_mcp.discovery import ToolEntry, register_one
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import register_facade
from axm_mcp.images import image_result
from axm_mcp.scoped import _backend_result
from axm_mcp.wrapping import build_wrappers


def png(width: int = 1, height: int = 1) -> bytes:
    buffer = io.BytesIO()
    with Image.new("RGB", (width, height), "red") as source:
        source.save(buffer, format="PNG")
    return buffer.getvalue()


class ResultTool:
    """Return a structural result as third-party tools may do."""

    name = "picture"

    def __init__(self, result: object) -> None:
        self.result = result

    def execute(self) -> object:
        return self.result


@pytest.mark.parametrize("facade", [False, True])
@pytest.mark.parametrize("malformed", ["tuple", "decode"])
async def test_malformed_image_is_a_tool_failure(facade: bool, malformed: str) -> None:
    images = (
        [ToolImage(png())]
        if malformed == "tuple"
        else (ToolImage(b"\x89PNG\r\n\x1a\njunk"),)
    )
    tool = cast(
        ToolEntry, ResultTool(SimpleNamespace(success=True, text="page", images=images))
    )
    server = MCPServer("image-refusals")
    register_one(server, "picture", tool)
    register_facade(server, ToolCatalog({"picture": tool}))
    result = await server.call_tool(
        "axm_call" if facade else "picture", {"name": "picture"} if facade else {}
    )
    assert isinstance(result, CallToolResult)
    assert not any(isinstance(block, ImageContent) for block in result.content)
    message = " ".join(
        block.text for block in result.content if isinstance(block, TextContent)
    )
    assert "false" in message.lower()
    assert "ValueError" in message
    assert "bad arguments" not in message
    wrapper, _ = build_wrappers("picture", tool, text_status=True)
    scoped = _backend_result(wrapper(), tool_result=True)
    assert scoped.is_error
    assert not any(isinstance(block, ImageContent) for block in scoped.content)


async def test_data_without_text_supports_paths_and_keeps_image() -> None:
    result = ToolResult(
        success=True, data={"file": Path("page.png")}, images=(ToolImage(png()),)
    )
    catalog = ToolCatalog({"picture": cast(ToolEntry, ResultTool(result))})
    answer = await catalog.acall("picture")
    assert isinstance(answer, CallToolResult)
    assert isinstance(answer.content[0], TextContent)
    assert "page.png" in answer.content[0].text
    assert isinstance(answer.content[1], ImageContent)


def test_dimensions_are_refused_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = png(4097, 1)

    def unexpected_load(*args: object, **kwargs: object) -> None:
        raise AssertionError("oversized image must not be decoded")

    monkeypatch.setattr(Image.Image, "load", unexpected_load)
    with pytest.raises(ValueError, match="4096"):
        image_result((ToolImage(data),), "page")


@pytest.mark.parametrize(
    "format_name,mime",
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
)
def test_supported_images_decode_before_transport(format_name: str, mime: str) -> None:
    buffer = io.BytesIO()
    with Image.new("RGB", (8, 8), "blue") as source:
        source.save(buffer, format=format_name)
    result = image_result((ToolImage(buffer.getvalue(), mime),), "page")
    assert isinstance(result.content[1], ImageContent)
    assert result.content[1].mime_type == mime


async def test_text_only_tools_have_no_inferred_output_schema() -> None:
    server = MCPServer("text-contract")
    tool = cast(
        ToolEntry,
        ResultTool(ToolResult(success=True, text="done", data={"private": "unused"})),
    )
    register_one(server, "picture", tool)
    register_facade(server, ToolCatalog({"picture": tool}))
    for definition in await server.list_tools():
        if definition.name in {"picture", "axm_call"}:
            assert definition.output_schema is None
    for name, arguments in [("picture", {}), ("axm_call", {"name": "picture"})]:
        result = await server.call_tool(name, arguments)
        assert result.structured_content is None
        assert result.content == [TextContent(type="text", text="done")]
