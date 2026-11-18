from __future__ import annotations

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
