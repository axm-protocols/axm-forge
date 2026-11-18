from __future__ import annotations

import json
from typing import cast

import pytest
from axm.tools.base import ToolResult
from mcp.server.mcpserver import MCPServer

from axm_mcp.discovery import ToolEntry, register_tools


class DualTool:
    mcp_dual_result = True

    def execute(self, fail: bool = False) -> ToolResult:
        return ToolResult(
            success=not fail,
            data={"success": "business", "data_success": "preserved", "data": {"x": 1}},
            error="typed failure" if fail else None,
            hint="try again" if fail else None,
            text="compact",
        )


class JsonFailureTool:
    mcp_dual_result = True

    def execute(self) -> ToolResult:
        return ToolResult(success=False, data={"item": 3}, error="bad", hint="retry")


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
