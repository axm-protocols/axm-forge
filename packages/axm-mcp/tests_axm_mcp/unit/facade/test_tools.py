"""Unit tests for facade tool registration and axm_call error handling."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.mcpserver import MCPServer

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog
from axm_mcp.facade.tools import FACADE_TOOLS, register_facade
from axm_mcp.session_contracts import SessionContractRegistry, WriteContract
from tests_axm_mcp.unit._helpers import _catalog


class _EchoTool:
    domain = "demo"
    tags = frozenset({"echo"})

    @property
    def name(self) -> str:
        return "echo"

    def execute(self, *, msg: str) -> ToolResult:
        """Echo a message back."""
        return ToolResult(success=True, data={"msg": msg}, text=f"echo: {msg}")


class _WriteFileProbe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def execute(self, *, path: str, file: str, content: str) -> ToolResult:
        self.calls.append((path, file))
        return ToolResult(success=True, text=content)


def _call_text(server: MCPServer, tool: str, **arguments: object) -> str:
    """Drive a facade tool through MCPServer and return its rendered text."""
    result = asyncio.run(server.call_tool(tool, arguments))
    blocks = getattr(result, "content", None)
    if blocks is None:
        blocks = result[0] if isinstance(result, tuple) else result
    return blocks[0].text if isinstance(blocks, list) else str(blocks)


@pytest.fixture
def server() -> MCPServer:
    mcp = MCPServer("test")
    register_facade(
        mcp,
        _catalog(
            echo=_EchoTool(),
            git_commit=_EchoTool(),
            nope_not_tool=_EchoTool(),
        ),
    )
    return mcp


def test_facade_tools_constant() -> None:
    assert set(FACADE_TOOLS) == {
        "axm_search",
        "axm_describe",
        "axm_call",
        "axm_capabilities",
    }


def test_four_tools_registered(server: MCPServer) -> None:
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"axm_search", "axm_describe", "axm_call", "axm_capabilities"} <= names


def test_call_via_fastmcp_returns_text(server: MCPServer) -> None:
    text = _call_text(server, "axm_call", name="echo", arguments={"msg": "hi"})
    assert "echo: hi" in text


def test_shared_facade_refuses_out_of_scope_path_without_executing_tool() -> None:
    """AC1: facade dispatch enforces the emitting session's write contract."""
    registry = SessionContractRegistry(clock=lambda: 0.0)
    registry.bind(
        "sess-a",
        WriteContract.from_mapping(
            {"execution_root": "/scope_a", "allowed_prefixes": ["/scope_a"]}
        ),
    )
    probe = _WriteFileProbe()
    catalog = ToolCatalog(
        {"write_file": cast(ToolEntry, probe)},
        shared_mode=True,
        write_contract_resolver=lambda: registry.resolve("sess-a"),
    )
    facade_server = MCPServer("shared-facade")
    register_facade(facade_server, catalog)

    rendered = _call_text(
        facade_server,
        "axm_call",
        name="write_file",
        arguments={"path": "/scope_b", "file": "x.txt", "content": "blocked"},
    )

    assert "success: False" in rendered
    assert "error:" in rendered and "/scope_b" in rendered
    assert probe.calls == []


def test_call_unknown_tool_returns_error(server: MCPServer) -> None:
    text = _call_text(server, "axm_call", name="nope", arguments={})
    assert "error" in text.lower()
    assert "nope" in text


def test_call_bad_args_includes_param_hint(server: MCPServer) -> None:
    # echo requires 'msg'; omit it -> error text should list accepted params.
    text = _call_text(server, "axm_call", name="echo", arguments={})
    assert "accepted params" in text.lower()
    assert "msg" in text


def test_describe_returns_compact_rendered_contract(server: MCPServer) -> None:
    """AC1: describe renders its header, signature, and docstring as text."""
    rendered = _call_text(server, "axm_describe", name="git_commit")

    assert rendered.startswith("git_commit | demo | echo")
    assert "msg: str" in rendered
    assert "Echo a message back." in rendered


def test_search_returns_rendered_text(server: MCPServer) -> None:
    """AC2: search returns the compact render_search text contract."""
    rendered = _call_text(server, "axm_search", query="git")

    assert rendered.startswith("axm_search | 1 hits\n")
    assert "git_commit [demo]" in rendered


def test_capabilities_returns_one_rendered_line_per_domain(server: MCPServer) -> None:
    """AC3: capabilities renders every domain on a single text line."""
    rendered = _call_text(server, "axm_capabilities")

    assert rendered.startswith("demo: ")
    assert set(rendered.removeprefix("demo: ").split()) == {
        "echo",
        "git_commit",
        "nope_not_tool",
    }
    assert "\n" not in rendered


def test_describe_unknown_returns_near_match_without_catalog_dump(
    server: MCPServer,
) -> None:
    """AC4: an unknown description is compact and suggests a near match."""
    rendered = _call_text(server, "axm_describe", name="nope_not_a_tool")

    assert "Did you mean: nope_not_tool" in rendered
    assert "echo" not in rendered
    assert "git_commit" not in rendered
