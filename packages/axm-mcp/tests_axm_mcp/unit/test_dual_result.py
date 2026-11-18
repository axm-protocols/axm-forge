from __future__ import annotations

import json
from typing import cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.mcpserver import MCPServer

from axm_mcp.discovery import ToolEntry, register_tools


class StructuredResult(ToolResult):
    mcp_structured = True


class DualTool:
    def execute(self, fail: bool = False) -> ToolResult:
        return StructuredResult(
            success=not fail,
            data={"success": "business", "data_success": "preserved", "data": {"x": 1}},
            error="typed failure" if fail else None,
            hint="try again" if fail else None,
            text="compact",
        )


class JsonFailureTool:
    def execute(self) -> ToolResult:
        return StructuredResult(
            success=False, data={"item": 3}, error="bad", hint="retry"
        )


class LegacyTool:
    def execute(self, json_mode: bool = False) -> ToolResult:
        return ToolResult(
            success=True, data={"item": 3}, text=None if json_mode else "compact"
        )


@pytest.mark.parametrize("fail", [False, True])
async def test_registered_dual_result_preserves_text_and_data(fail: bool) -> None:
    server = MCPServer("dual")
    register_tools(server, {"dual": cast(ToolEntry, DualTool())})
    result = await server.call_tool("dual", {"fail": fail})
    assert result.is_error is fail
    assert result.content[0].text == (
        "✗ typed failure\ncompact\nhint: try again" if fail else "compact"
    )
    assert result.structured_content == {
        "data": {"success": "business", "data_success": "preserved", "data": {"x": 1}},
        "success": not fail,
        **({"error": "typed failure", "hint": "try again"} if fail else {}),
    }


async def test_registered_failure_without_text_keeps_legacy_json() -> None:
    server = MCPServer("dual")
    register_tools(server, {"dual": cast(ToolEntry, JsonFailureTool())})
    result = await server.call_tool("dual", {})
    assert result.is_error is True
    assert json.loads(result.content[0].text) == {
        "item": 3,
        "success": False,
        "error": "bad",
        "hint": "retry",
    }
    assert result.structured_content == {
        "data": {"item": 3},
        "success": False,
        "error": "bad",
        "hint": "retry",
    }


@pytest.mark.parametrize("json_mode", [False, True])
async def test_registered_legacy_modes_do_not_emit_structured(json_mode: bool) -> None:
    server = MCPServer("legacy")
    register_tools(server, {"legacy": cast(ToolEntry, LegacyTool())})
    result = await server.call_tool("legacy", {"json_mode": json_mode})
    assert result.structured_content is None
    if json_mode:
        assert json.loads(result.content[0].text) == {"item": 3, "success": True}
    else:
        assert result.content[0].text == "compact"
