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


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python package for tool testing."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)

    (pkg / "__init__.py").write_text(
        '"""Demo package."""\n\n__all__ = ["greet"]\n\nfrom demo.core import greet\n'
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
        "        greet('world')\n\n"
        "    @property\n"
        "    def label(self) -> str:\n"
        '        """Helper label."""\n'
        '        return "helper"\n\n'
        "    @classmethod\n"
        "    def from_name(cls, name: str) -> 'Helper':\n"
        '        """Create from name."""\n'
        "        return cls()\n\n"
        "    @staticmethod\n"
        "    def version() -> str:\n"
        '        """Return version."""\n'
        '        return "1.0"\n'
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

    # --- Slim mode (AXM-132) ---

    def test_context_tool_slim(self, sample_project: Path) -> None:
        """AC1+4: slim=True returns compact data with top_modules."""
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), slim=True)
        assert result.success is True
        assert "top_modules" in result.data
        assert "modules" not in result.data

    def test_context_tool_default_unchanged(self, sample_project: Path) -> None:
        """AC4: default behavior unchanged (regression)."""
        from axm_ast.tools.context import ContextTool

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # depth=1 (default) returns 'packages' grouping, not raw 'modules'
        assert "packages" in result.data
        assert "patterns" in result.data


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

    def test_execute_detailed_includes_docstrings(self, sample_project: Path) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), detail="detailed"
        )
        assert result.success is True
        # Find core module with greet function
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None, "core module not found"
        greet_fn = next(
            (f for f in core_mod["functions"] if f["name"] == "greet"), None
        )
        assert greet_fn is not None, "greet function not found"
        assert "summary" in greet_fn
        assert greet_fn["summary"] == "Say hello."

    def test_execute_summary_excludes_docstrings(self, sample_project: Path) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), detail="summary"
        )
        assert result.success is True
        for mod in result.data["modules"]:
            for fn in mod.get("functions", []):
                msg = f"summary unexpectedly present in {fn['name']}"
                assert "summary" not in fn, msg

    def test_execute_default_detail_is_summary(self, sample_project: Path) -> None:
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # Default should return signatures only (detail="summary"), no docstrings
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None
        greet_fn = next(
            (f for f in core_mod["functions"] if f["name"] == "greet"), None
        )
        assert greet_fn is not None
        assert "signature" in greet_fn
        assert "summary" not in greet_fn

    # --- TOC mode (AXM-131) ---

    def test_describe_tool_toc(self, sample_project: Path) -> None:
        """AC1: detail='toc' returns module list with counts."""
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), detail="toc")
        assert result.success is True
        assert "modules" in result.data
        assert "module_count" in result.data
        entry = result.data["modules"][0]
        assert "name" in entry
        assert "symbol_count" in entry
        assert "function_count" in entry
        assert "class_count" in entry
        # Must NOT have functions/classes arrays
        assert "functions" not in entry
        assert "classes" not in entry

    def test_describe_tool_modules_filter(self, sample_project: Path) -> None:
        """AC3: modules=['core'] returns only core modules."""
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), modules=["core"]
        )
        assert result.success is True
        for mod in result.data["modules"]:
            assert "core" in mod["name"].lower()

    def test_describe_tool_toc_plus_filter(self, sample_project: Path) -> None:
        """AC4: detail='toc' + modules=['core'] combines both."""
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            detail="toc",
            modules=["core"],
        )
        assert result.success is True
        for entry in result.data["modules"]:
            assert "core" in entry["name"].lower()
            assert "functions" not in entry

    def test_describe_tool_default_unchanged(self, sample_project: Path) -> None:
        """AC5: default behavior unchanged (regression)."""
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # Must have full module data with functions/classes arrays
        core_mod = next(
            (m for m in result.data["modules"] if m["name"] == "core"), None
        )
        assert core_mod is not None
        assert "functions" in core_mod
        assert "classes" in core_mod

    def test_describe_tool_filter_no_match(self, sample_project: Path) -> None:
        """Edge: non-matching filter returns empty list, success=True."""
        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            modules=["nonexistent_xyz"],
        )
        assert result.success is True
        assert result.data["module_count"] == 0


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

    # --- Batch mode (AXM-462) ---

    def test_symbols_batch_success(self, sample_project: Path) -> None:
        """AC1/2: Batch with two valid symbols returns severity for each."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbols=["greet", "Helper"],
        )
        assert result.success is True
        assert "symbols" in result.data
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert "severity" in symbols[0]
        assert "severity" in symbols[1]

    def test_symbols_batch_partial_missing(self, sample_project: Path) -> None:
        """AC2: Batch with one valid + one missing → mixed results."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbols=["greet", "missing_xyz"],
        )
        assert result.success is True
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert "severity" in symbols[0]
        assert "error" in symbols[1]
        assert symbols[1]["symbol"] == "missing_xyz"

    def test_symbols_invalid_type(self) -> None:
        """AC5: symbols must be a list, else error."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=".", symbols="not_a_list")  # type: ignore[arg-type]
        assert result.success is False
        assert result.error is not None
        assert "must be a list" in result.error

    def test_symbols_precedence(self, sample_project: Path) -> None:
        """Edge: Both symbol and symbols → symbols takes precedence."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbol="greet",
            symbols=["Helper"],
        )
        assert result.success is True
        assert "symbols" in result.data
        assert len(result.data["symbols"]) == 1

    def test_symbols_empty_list(self) -> None:
        """Edge: Empty symbols list falls through to require symbol param."""
        from axm_ast.tools.impact import ImpactTool

        tool = ImpactTool()
        result = tool.execute(path=".", symbols=[])
        assert result.success is False
        assert "required" in result.error  # type: ignore[operator]


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

    def test_inspect_dotted_method(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "run"

    def test_inspect_dotted_property(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.label"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "label"

    def test_inspect_dotted_classmethod(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.from_name"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "from_name"

    def test_inspect_dotted_not_found(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "nonexistent" in result.error
        assert "Helper" in result.error

    def test_inspect_class_not_found_dotted(self, sample_project: Path) -> None:
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Missing.method"
        )
        assert result.success is False
        assert result.error is not None
        assert "Missing" in result.error

    def test_inspect_toplevel_unchanged(self, sample_project: Path) -> None:
        """Regression: top-level symbols still work (AC5)."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    # --- Module.function resolution (AXM-54) ---

    def test_inspect_module_function(self, sample_project: Path) -> None:
        """AC1: core.greet resolves to greet in core module."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.greet"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    def test_inspect_module_class(self, sample_project: Path) -> None:
        """AC2: core.Helper resolves to Helper class in core module."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.Helper"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "Helper"

    def test_inspect_module_symbol_not_found(self, sample_project: Path) -> None:
        """Module found but symbol does not exist in it."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="core.nonexistent"
        )
        assert result.success is False
        assert result.error is not None
        assert "core" in result.error
        assert "nonexistent" in result.error

    def test_inspect_unknown_module_falls_back_to_class(
        self, sample_project: Path
    ) -> None:
        """AC4: unknown prefix falls back to ClassName.method."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        # Helper.run should still work via class method fallback
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert result.success is True
        assert result.data["symbol"]["name"] == "run"

    def test_inspect_no_match_at_all(self, sample_project: Path) -> None:
        """No module and no class matches → combined error."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="nonexistent.xyz"
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    # --- Line info and source (AXM-396) ---

    def test_inspect_includes_line_info(self, sample_project: Path) -> None:
        """AC1: inspect returns file, start_line, end_line for a function."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        assert result.success is True
        sym = result.data["symbol"]
        assert "file" in sym
        assert "start_line" in sym
        assert "end_line" in sym
        assert sym["start_line"] > 0
        assert sym["end_line"] >= sym["start_line"]
        assert "core.py" in sym["file"]

    def test_inspect_class_line_info(self, sample_project: Path) -> None:
        """AC1+AC4: class line info spans full class body."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["start_line"] > 0
        assert sym["end_line"] > sym["start_line"]  # multi-line class

    def test_inspect_method_line_info(self, sample_project: Path) -> None:
        """AC4: method line info is for the method only, not the class."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        cls_result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper"
        )
        method_result = tool.execute(
            path=str(sample_project / "src" / "demo"), symbol="Helper.run"
        )
        assert cls_result.success is True
        assert method_result.success is True
        cls_sym = cls_result.data["symbol"]
        method_sym = method_result.data["symbol"]
        # Method lines are within class lines
        assert method_sym["start_line"] >= cls_sym["start_line"]
        assert method_sym["end_line"] <= cls_sym["end_line"]

    def test_inspect_source_true(self, sample_project: Path) -> None:
        """AC2: source=True includes source code."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"),
            symbol="greet",
            source=True,
        )
        assert result.success is True
        sym = result.data["symbol"]
        assert "source" in sym
        assert "def greet" in sym["source"]
        assert "Hello" in sym["source"]

    def test_inspect_source_false_default(self, sample_project: Path) -> None:
        """AC3: source is absent by default."""
        from axm_ast.tools.inspect import InspectTool

        tool = InspectTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        assert result.success is True
        assert "source" not in result.data["symbol"]


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

    # --- Progressive disclosure (detail + pages) ---

    def test_docs_toc_returns_headings_not_content(self, sample_project: Path) -> None:
        """detail='toc' returns headings + line_count, NOT content."""
        # Create docs/ with a markdown file
        docs = sample_project / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide\n\n## Getting Started\n\nSome text.\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="toc")
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        page = pages[0]
        assert "headings" in page
        assert "line_count" in page
        assert "content" not in page

    def test_docs_summary_returns_summaries(self, sample_project: Path) -> None:
        """detail='summary' returns headings + first sentences."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "api.md").write_text(
            "# API Reference\n\nFull API docs.\n\n"
            "## Functions\n\nAll public functions.\n"
        )

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="summary")
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        page = pages[0]
        assert "headings" in page
        assert "summaries" in page
        assert "content" not in page

    def test_docs_full_returns_content(self, sample_project: Path) -> None:
        """detail='full' (default) returns full content."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "intro.md").write_text("# Intro\n\nHello.\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project))
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) >= 1
        assert "content" in pages[0]

    def test_docs_pages_filter(self, sample_project: Path) -> None:
        """pages=['guide'] filters to matching pages only."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "guide.md").write_text("# Guide\n")
        (docs / "api.md").write_text("# API\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), pages=["guide"])
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) == 1
        assert "guide" in pages[0]["path"]

    def test_docs_toc_with_pages_filter(self, sample_project: Path) -> None:
        """detail='toc' + pages=['api'] combines both filters."""
        docs = sample_project / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "guide.md").write_text("# Guide\n")
        (docs / "api.md").write_text("# API\n\n## Endpoints\n")

        from axm_ast.tools.docs import DocsTool

        tool = DocsTool()
        result = tool.execute(path=str(sample_project), detail="toc", pages=["api"])
        assert result.success is True
        pages = result.data.get("pages", [])
        assert len(pages) == 1
        assert "content" not in pages[0]
        assert len(pages[0]["headings"]) == 2


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

    def test_toc_size_under_2k(self) -> None:
        """AC2: TOC output < 2048 bytes on axm-ast itself."""
        import json

        from axm_ast.tools.describe import DescribeTool

        tool = DescribeTool()
        result = tool.execute(path=str(SELF_PKG), detail="toc")
        assert result.success is True
        raw = json.dumps(result.data)
        assert len(raw) < 7168, f"TOC output too large: {len(raw)} bytes"


"""Tests for axm-ast MCP tool wrappers."""
