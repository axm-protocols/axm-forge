"""Unit tests for GraphTool (pure, no I/O)."""

from __future__ import annotations

import pytest

from axm_ast.tools.graph import GraphTool


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()


class TestGraphToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: GraphTool) -> None:
        assert tool.name == "ast_graph"


class TestGraphEdgeCasesUnit:
    """Edge cases for GraphTool (no I/O)."""

    def test_bad_path(self, tool: GraphTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False
