"""Unit tests for axm_ast.tools.callees."""

from __future__ import annotations


class TestCalleesMCPToolUnit:
    """Pure unit tests for CalleesTool — no I/O."""

    def test_mcp_tool_missing_symbol(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        tool = CalleesTool()
        result = tool.execute(path=".")
        assert result.success is False
        assert "symbol" in (result.error or "").lower()
