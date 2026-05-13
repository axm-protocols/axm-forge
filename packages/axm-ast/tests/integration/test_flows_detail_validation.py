"""Integration tests extracted from test_flows_detail_validation."""

from __future__ import annotations

from axm_ast.hooks.flows import FlowsHook
from axm_ast.tools.flows import FlowsTool


class TestFlowsToolInvalidDetail:
    """FlowsTool.execute() returns failure for invalid detail."""

    def test_flows_tool_invalid_detail(self, tmp_path: object) -> None:
        tool = FlowsTool()
        result = tool.execute(path=str(tmp_path), entry="main", detail="full")
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()


class TestDetailEdgeCasesIntegration:
    """Boundary conditions for detail validation (integration)."""

    def test_flows_hook_invalid_detail(self, tmp_path: object) -> None:
        hook = FlowsHook()
        result = hook.execute(
            context={"working_dir": str(tmp_path)},
            entry="main",
            detail="full",
        )
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()
