"""Integration tests for type parity between ToolCatalog and MCPServer."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.mcpserver import MCPServer

from axm_mcp.discovery import ToolEntry, discover_tools, register_one
from axm_mcp.facade.catalog import ToolCatalog

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class _ScalarTool:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, count: int) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, text=str(count))


class _ListTool:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, symbols: list[str]) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, text=str(symbols))


class _Record(TypedDict):
    label: str


class _NestedTool:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, records: list[_Record]) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, text=str(records))


class _CoercionTool:
    def __init__(self) -> None:
        self.received: list[int] = []

    def execute(self, *, items: int) -> ToolResult:
        self.received.append(items)
        return ToolResult(success=True, text=str(items))


def _dual_harness(name: str, tool: object) -> tuple[MCPServer, ToolCatalog]:
    entry = cast(ToolEntry, tool)
    server = MCPServer(f"parity-{name}")
    register_one(server, name, entry)
    return server, ToolCatalog({name: entry})


async def _direct_error(
    server: MCPServer, name: str, arguments: dict[str, object]
) -> Exception:
    with pytest.raises(Exception) as captured:
        await server.call_tool(name, arguments)
    return captured.value


def _facade_error(
    catalog: ToolCatalog, name: str, arguments: dict[str, object]
) -> Exception:
    with pytest.raises(Exception) as captured:
        catalog.call(name, arguments)
    return captured.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ast_impact_rejects_invalid_symbols_through_both_gates() -> None:
    """AC1: ast_impact rejects integer symbols before either path executes."""
    tool = discover_tools()["ast_impact"]
    server, catalog = _dual_harness("ast_impact", tool)
    arguments: dict[str, object] = {
        "path": str(_PACKAGE_ROOT),
        "symbols": [123, 456],
    }

    direct_error = await _direct_error(server, "ast_impact", arguments)
    facade_error = _facade_error(catalog, "ast_impact", arguments)

    assert type(facade_error) is type(direct_error)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scalar_mistype_has_the_same_rejection_verdict() -> None:
    """AC2: scalar type errors are rejected identically before execute."""
    tool = _ScalarTool()
    server, catalog = _dual_harness("scalar", tool)
    arguments = {"count": "not-an-int"}

    direct_error = await _direct_error(server, "scalar", arguments)
    assert tool.calls == 0
    facade_error = _facade_error(catalog, "scalar", arguments)

    assert type(facade_error) is type(direct_error)
    assert tool.calls == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_item_mistype_has_the_same_rejection_verdict() -> None:
    """AC3: list item type errors are rejected identically before execute."""
    tool = _ListTool()
    server, catalog = _dual_harness("list_items", tool)
    arguments = {"symbols": [123]}

    direct_error = await _direct_error(server, "list_items", arguments)
    assert tool.calls == 0
    facade_error = _facade_error(catalog, "list_items", arguments)

    assert type(facade_error) is type(direct_error)
    assert tool.calls == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malformed_nested_object_has_the_same_rejection_verdict() -> None:
    """AC4: malformed nested objects are rejected identically before execute."""
    tool = _NestedTool()
    server, catalog = _dual_harness("nested", tool)
    arguments = {"records": [{"wrong_key": "value"}]}

    direct_error = await _direct_error(server, "nested", arguments)
    assert tool.calls == 0
    facade_error = _facade_error(catalog, "nested", arguments)

    assert type(facade_error) is type(direct_error)
    assert tool.calls == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coercible_scalar_has_the_same_accepted_shape() -> None:
    """AC5: both gates decode a coercible JSON list before execute."""
    tool = _CoercionTool()
    server, catalog = _dual_harness("coercion", tool)
    arguments = {"items": True}

    await server.call_tool("coercion", arguments)
    catalog.call("coercion", arguments)

    assert tool.received == [1, 1]
    assert all(type(item) is int for item in tool.received)
