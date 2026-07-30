"""Unit tests for facade tool registration and axm_call error handling."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.fastmcp import FastMCP

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import FACADE_TOOLS, register_facade


class _EchoTool:
    domain = "demo"
    tags = frozenset({"echo"})

    @property
    def name(self) -> str:
        return "echo"

    def execute(self, *, msg: str) -> ToolResult:
        """Echo a message back."""
        return ToolResult(success=True, data={"msg": msg}, text=f"echo: {msg}")


def _catalog(**tools: object) -> ToolCatalog:
    """Build a catalog from fake tools, casting to the ToolEntry contract."""
    return ToolCatalog({k: cast(ToolEntry, v) for k, v in tools.items()})


def _call_text(server: FastMCP, tool: str, **arguments: object) -> str:
    """Drive a facade tool through FastMCP and return its rendered text."""
    result = asyncio.run(server.call_tool(tool, arguments))
    blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text if isinstance(blocks, list) else str(blocks)


@pytest.fixture
def server() -> FastMCP:
    mcp = FastMCP("test")
    register_facade(mcp, _catalog(echo=_EchoTool()))
    return mcp


def test_facade_tools_constant() -> None:
    assert set(FACADE_TOOLS) == {
        "axm_search",
        "axm_describe",
        "axm_call",
        "axm_capabilities",
    }


def test_four_tools_registered(server: FastMCP) -> None:
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"axm_search", "axm_describe", "axm_call", "axm_capabilities"} <= names


def test_call_via_fastmcp_returns_text(server: FastMCP) -> None:
    text = _call_text(server, "axm_call", name="echo", arguments={"msg": "hi"})
    assert "echo: hi" in text


def test_call_unknown_tool_returns_error(server: FastMCP) -> None:
    text = _call_text(server, "axm_call", name="nope", arguments={})
    assert "error" in text.lower()
    assert "nope" in text


def test_call_bad_args_includes_param_hint(server: FastMCP) -> None:
    # echo requires 'msg'; omit it -> error text should list accepted params.
    text = _call_text(server, "axm_call", name="echo", arguments={})
    assert "accepted params" in text.lower()
    assert "msg" in text


def test_describe_unknown_returns_error_dict() -> None:
    mcp = FastMCP("t")
    register_facade(mcp, _catalog())
    rendered = _call_text(mcp, "axm_describe", name="ghost")
    assert "ghost" in rendered or "error" in rendered.lower()
