"""Unit tests for :class:`axm_mcp.verify.VerifyTool`."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from axm.tools.base import ToolResult

from axm_mcp.verify import VerifyTool


def _audit_tool() -> MagicMock:
    tool = MagicMock()
    tool.execute.return_value = ToolResult(
        success=True,
        data={
            "score": 80,
            "grade": "B",
            "passed": ["ok1", "ok2"],
            "failed": [
                {
                    "rule_id": "QUALITY_TYPE",
                    "message": "5 errors",
                    "text": "• untested: foo.py",
                    "fix_hint": "Add type hints",
                }
            ],
        },
    )
    return tool


def _init_tool() -> MagicMock:
    tool = MagicMock()
    tool.execute.return_value = ToolResult(
        success=True,
        data={"score": 100, "grade": "A", "passed_count": 3, "failed": []},
    )
    return tool


class TestVerifyTool:
    def test_name(self) -> None:
        assert VerifyTool().name == "verify"

    def test_execute_returns_tool_result(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert isinstance(result, ToolResult)
        assert result.success is True

    def test_execute_data_preserved(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert "audit" in result.data
        assert "governance" in result.data
        assert result.data["audit"]["grade"] == "B"

    def test_execute_text_non_null_and_compact(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert result.text is not None
        assert result.text.startswith("verify | audit B 80")
        assert "✗ QUALITY_TYPE" in result.text

    def test_execute_with_no_tools(self) -> None:
        result = VerifyTool({}).execute(path="/tmp/fake")
        assert result.success is True
        assert result.data["audit"] is None
        assert result.data["governance"] is None
        assert result.text is not None
        assert "audit: skipped" in result.text
