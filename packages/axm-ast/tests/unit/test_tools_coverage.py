"""Stub - tests moved here by axm-anvil."""

import pytest

from axm_ast.tools.callers import CallersTool
from axm_ast.tools.doc_impact import DocImpactTool
from axm_ast.tools.flows import FlowsTool


@pytest.fixture()
def doc_impact_tool() -> DocImpactTool:
    return DocImpactTool()


@pytest.fixture()
def flows_tool() -> FlowsTool:
    return FlowsTool()


@pytest.fixture()
def callers_tool() -> CallersTool:
    return CallersTool()


class TestDocImpactToolEdgeCasesUnit:
    """DocImpactTool edge cases — name, empty symbols, bad path."""

    def test_name(self, doc_impact_tool: DocImpactTool) -> None:
        assert doc_impact_tool.name == "ast_doc_impact"

    def test_empty_symbols(self, doc_impact_tool: DocImpactTool) -> None:
        result = doc_impact_tool.execute(path=".")
        assert result.success is False
        assert "symbols" in (result.error or "")

    def test_bad_path(self, doc_impact_tool: DocImpactTool) -> None:
        result = doc_impact_tool.execute(path="/nonexistent/path/xyz", symbols=["foo"])
        assert result.success is False


class TestCalleesToolEdgeCasesUnit:
    """CalleesTool — name, bad path."""

    def test_name(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        assert CalleesTool().name == "ast_callees"

    def test_bad_path(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        result = CalleesTool().execute(path="/nonexistent/path/xyz", symbol="foo")
        assert result.success is False


class TestFlowsToolEdgeCases:
    """FlowsTool — name, bad path."""

    def test_name(self, flows_tool: FlowsTool) -> None:
        assert flows_tool.name == "ast_flows"

    def test_bad_path(self, flows_tool: FlowsTool) -> None:
        result = flows_tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False


class TestCallersToolEdgeCasesUnit:
    """CallersTool — bad path."""

    def test_bad_path(self, callers_tool: CallersTool) -> None:
        result = callers_tool.execute(path="/nonexistent/path/xyz", symbol="foo")
        assert result.success is False
