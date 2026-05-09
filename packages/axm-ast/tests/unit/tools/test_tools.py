"""Unit tests for tool wrappers (no I/O)."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SELF_PKG = Path(__file__).resolve().parents[3] / "src" / "axm_ast"
SELF_ROOT = Path(__file__).resolve().parents[3]


class TestContextToolUnit:
    """Tests for ast_context tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        assert tool.name == "ast_context"

    def test_is_axm_tool(self) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        assert hasattr(tool, "execute")
        assert hasattr(tool, "name")

    def test_execute_bad_path(self) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False
        assert result.error is not None


class TestDescribeToolUnit:
    """Tests for ast_describe tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        assert tool.name == "ast_describe"

    def test_execute_bad_path(self) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


class TestSearchToolUnit:
    """Tests for ast_search tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        assert tool.name == "ast_search"


class TestCallersToolUnit:
    """Tests for ast_callers tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.callers import CallersTool

        tool = CallersTool()
        assert tool.name == "ast_callers"


class TestImpactToolUnit:
    """Tests for ast_impact tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        assert tool.name == "ast_impact"

    def test_symbols_invalid_type(self) -> None:
        """AC5: symbols must be a list, else error."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=".", symbols="not_a_list")
        assert result.success is False
        assert result.error is not None
        assert "must be a list" in result.error

    def test_symbols_empty_list(self) -> None:
        """Edge: Empty symbols list falls through to require symbol param."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=".", symbols=[])
        assert result.success is False
        assert "required" in result.error


class TestInspectToolUnit:
    """Tests for ast_inspect tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        assert tool.name == "ast_inspect"


class TestGraphToolUnit:
    """Tests for ast_graph tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.graph import GraphTool

        tool = GraphTool()
        assert tool.name == "ast_graph"


class TestDocsToolUnit:
    """Tests for ast_docs tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        assert tool.name == "ast_docs"

    def test_docs_bad_path(self) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


class TestDogfoodUnit:
    """Run tools on the axm-ast package itself."""

    def test_context_on_self(self) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path=str(SELF_PKG))
        assert result.success is True
        assert result.data["name"] == "axm_ast"

    def test_describe_on_self(self) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(SELF_PKG), compress=True)
        assert result.success is True
        assert result.data["module_count"] >= 16

    def test_docs_on_self(self) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(SELF_ROOT))
        assert result.success is True
        assert result.data["readme"] is not None
