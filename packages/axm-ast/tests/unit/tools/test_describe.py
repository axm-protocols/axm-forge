"""Unit tests for DescribeTool — pure (no I/O)."""

from __future__ import annotations

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture()
def tool() -> DescribeTool:
    """Provide a fresh DescribeTool instance."""
    return DescribeTool()


class TestDescribeToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: DescribeTool) -> None:
        assert tool.name == "ast_describe"

    def test_has_agent_hint(self, tool: DescribeTool) -> None:
        assert tool.agent_hint


class TestDescribeToolBadPath:
    """Bad path edge case (no filesystem I/O)."""

    def test_bad_path(self, tool: DescribeTool) -> None:
        result = tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False
