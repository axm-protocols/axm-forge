"""Unit tests for axm_ast.tools.flows — pure (no I/O)."""

from __future__ import annotations

import pytest

from axm_ast.tools.flows import FlowsTool


@pytest.fixture()
def flows_tool() -> FlowsTool:
    return FlowsTool()


class TestFlowsToolEdgeCases:
    """FlowsTool — name, bad path."""

    def test_name(self, flows_tool: FlowsTool) -> None:
        assert flows_tool.name == "ast_flows"

    def test_bad_path(self, flows_tool: FlowsTool) -> None:
        result = flows_tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False
