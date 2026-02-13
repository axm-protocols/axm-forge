"""Tests for axm-ast MCP tool wrappers.

Each tool is an AXMTool subclass exposing core functions
via the axm.tools entry point system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SELF_PKG = Path(__file__).resolve().parent.parent / "src" / "axm_ast"
SELF_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()  # type: ignore[misc]
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python package for tool testing."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)

    (pkg / "__init__.py").write_text(
        '"""Demo package."""\n\n'
        '__all__ = ["greet"]\n\n'
        "from demo.core import greet\n"
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        '__all__ = ["greet", "Helper"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n\n\n'
        "class Helper:\n"
        '    """A helper class."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run the helper."""\n'
        "        greet('world')\n"
    )

    # Add a pyproject.toml for context tool
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )

    # Add a README for docs tool
    (tmp_path / "README.md").write_text("# Demo\n\nA demo project.\n")

    return tmp_path


# ---------------------------------------------------------------------------
# Helper: check ToolResult shape
# ---------------------------------------------------------------------------


def _assert_tool_result(result: Any) -> None:
    """Assert result is a valid ToolResult."""
    assert hasattr(result, "success")
    assert hasattr(result, "data")
    assert isinstance(result.data, dict)


# ===========================================================================
# ast_context
# ===========================================================================


class TestContextTool:
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

    def test_execute_returns_tool_result(self, sample_project: Path) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True

    def test_execute_has_name_key(self, sample_project: Path) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert "name" in result.data

    def test_execute_bad_path(self) -> None:
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False
        assert result.error is not None


# ===========================================================================
# ast_describe
# ===========================================================================


class TestDescribeTool:
    """Tests for ast_describe tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        assert tool.name == "ast_describe"

    def test_execute_returns_modules(self, sample_project: Path) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True
        assert "modules" in result.data

    def test_execute_compress_mode(self, sample_project: Path) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), compress=True)
        assert result.success is True
        assert "compressed" in result.data

    def test_execute_bad_path(self) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


# ===========================================================================
# ast_search
# ===========================================================================


class TestSearchTool:
    """Tests for ast_search tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        assert tool.name == "ast_search"

    def test_search_by_name(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), name="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "results" in result.data
        assert result.data["count"] >= 1

    def test_search_by_returns(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), returns="str")
        assert result.success is True
        assert result.data["count"] >= 1

    def test_search_no_results(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), name="nonexistent_xyz"
        )
        assert result.success is True
        assert result.data["count"] == 0


# ===========================================================================
# ast_callers
# ===========================================================================


class TestCallersTool:
    """Tests for ast_callers tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.callers import CallersTool

        tool = CallersTool()
        assert tool.name == "ast_callers"

    def test_find_callers(self, sample_project: Path) -> None:
        from axm_ast.tools.callers import CallersTool

        tool = CallersTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "callers" in result.data
        assert result.data["count"] >= 1

    def test_missing_symbol(self, sample_project: Path) -> None:
        from axm_ast.tools.callers import CallersTool

        tool = CallersTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is False
        assert result.error is not None


# ===========================================================================
# ast_impact
# ===========================================================================


class TestImpactTool:
    """Tests for ast_impact tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        assert tool.name == "ast_impact"

    def test_analyze_impact(self, sample_project: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "severity" in result.data

    def test_missing_symbol(self, sample_project: Path) -> None:
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is False


# ===========================================================================
# ast_inspect
# ===========================================================================


class TestInspectTool:
    """Tests for ast_inspect tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        assert tool.name == "ast_inspect"

    def test_inspect_function(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "symbol" in result.data

    def test_inspect_class(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "Helper"

    def test_missing_symbol_param(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is False


# ===========================================================================
# ast_graph
# ===========================================================================


class TestGraphTool:
    """Tests for ast_graph tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.graph import GraphTool

        tool = GraphTool()
        assert tool.name == "ast_graph"

    def test_graph_returns_edges(self, sample_project: Path) -> None:
        from axm_ast.tools.graph import GraphTool

        tool = GraphTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True
        assert "graph" in result.data

    def test_graph_mermaid_format(self, sample_project: Path) -> None:
        from axm_ast.tools.graph import GraphTool

        tool = GraphTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), format="mermaid"
        )
        assert result.success is True
        assert "mermaid" in result.data


# ===========================================================================
# ast_docs
# ===========================================================================


class TestDocsTool:
    """Tests for ast_docs tool."""

    def test_has_name(self) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        assert tool.name == "ast_docs"

    def test_docs_returns_readme(self, sample_project: Path) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project))
        _assert_tool_result(result)
        assert result.success is True
        assert "readme" in result.data

    def test_docs_bad_path(self) -> None:
        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


# ===========================================================================
# Dogfood: run tools on axm-ast itself
# ===========================================================================


class TestDogfood:
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


"""Tests for axm-ast MCP tool wrappers."""
