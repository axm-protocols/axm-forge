"""Unit tests for the DeadCodeTool MCP wrapper (no I/O)."""

from __future__ import annotations

import pytest

from axm_ast.tools.dead_code import DeadCodeTool


@pytest.fixture()
def tool() -> DeadCodeTool:
    """Provide a fresh DeadCodeTool instance."""
    return DeadCodeTool()


class TestDeadCodeToolEdgeCasesUnit:
    """Edge cases for DeadCodeTool (pure, no I/O)."""

    def test_bad_path(self, tool: DeadCodeTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False
