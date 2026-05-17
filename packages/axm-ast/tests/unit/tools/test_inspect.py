"""Unit tests for InspectTool — no real I/O."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from axm.tools.base import ToolResult

from axm_ast.tools.inspect import InspectTool


@pytest.fixture()
def tool() -> InspectTool:
    """Provide a fresh InspectTool instance."""
    return InspectTool()


@pytest.fixture
def mock_pkg() -> MagicMock:
    """Minimal PackageInfo with modules for resolution tests."""
    pkg = MagicMock()

    mod_alpha = MagicMock()
    mod_alpha.path = "/fake/src/pkg/alpha.py"
    mod_alpha.docstring = "Alpha"
    mod_alpha.functions = [MagicMock(name="fn_a")]
    mod_alpha.classes = []

    mod_beta = MagicMock()
    mod_beta.path = "/fake/src/pkg/beta.py"
    mod_beta.docstring = "Beta"
    mod_beta.functions = []
    mod_beta.classes = [MagicMock(name="Cls")]

    mod_alpha_v2 = MagicMock()
    mod_alpha_v2.path = "/fake/src/pkg/alpha_v2.py"
    mod_alpha_v2.docstring = ""
    mod_alpha_v2.functions = []
    mod_alpha_v2.classes = []

    pkg.modules = [mod_alpha, mod_beta, mod_alpha_v2]
    pkg.module_names = ["pkg.alpha", "pkg.beta", "pkg.alpha_v2"]
    return pkg


# ---------------------------------------------------------------------------
# Edge cases — public execute()
# ---------------------------------------------------------------------------


class TestInspectEdgeCasesUnit:
    """Edge cases for InspectTool (no real I/O)."""

    def test_missing_symbol_param(self, tool: InspectTool) -> None:
        result = tool.execute(path=".")
        assert result.success is False
        assert result.error is not None
        assert "required" in result.error

    def test_symbols_invalid_type(self, tool: InspectTool) -> None:
        result = tool.execute(path=".", symbols="not_a_list")
        assert result.success is False
        assert result.error is not None
        assert "must be a list" in result.error

    def test_bad_path(self, tool: InspectTool) -> None:
        result = tool.execute(path="/nonexistent/path", symbol="foo")
        assert result.success is False


# ---------------------------------------------------------------------------
# Detail builders — _variable_detail / _function_detail / _class_detail
# ---------------------------------------------------------------------------


class TestVariableDetail:
    """Tests for InspectTool._variable_detail (extracted from _build_detail)."""

    def test_variable_detail_keys(self) -> None:
        """_variable_detail returns dict with expected keys."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="MY_CONST", line=10, annotation="int", value_repr="42")
        detail = InspectTool._variable_detail(var, file="mod.py")
        assert detail["name"] == "MY_CONST"
        assert detail["file"] == "mod.py"
        assert detail["kind"] == "variable"
        assert detail["start_line"] == 10
        assert detail["end_line"] == 10
        assert "module" not in detail

    def test_variable_without_annotation(self) -> None:
        """No annotation key when annotation is None."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="x", line=1, annotation=None, value_repr="1")
        detail = InspectTool._variable_detail(var, file="a.py")
        assert "annotation" not in detail

    def test_variable_with_annotation(self) -> None:
        """Annotation key present when set."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="x", line=1, annotation="str", value_repr=None)
        detail = InspectTool._variable_detail(var, file="a.py")
        assert detail["annotation"] == "str"


class TestFunctionDetail:
    """Tests for InspectTool._function_detail (extracted from _build_detail)."""

    def test_function_detail_params(self) -> None:
        """_function_detail includes signature and parameters list."""
        from axm_ast.models.nodes import FunctionInfo, ParameterInfo

        fn = FunctionInfo(
            name="greet",
            line_start=5,
            line_end=8,
            return_type="str",
            params=[ParameterInfo(name="name", annotation="str", default=None)],
            docstring="Say hello.",
        )
        detail = InspectTool._function_detail(fn, file="core.py")
        assert detail["name"] == "greet"
        assert detail["signature"] == "def greet(name: str) -> str"
        assert len(detail["parameters"]) == 1
        assert detail["parameters"][0]["name"] == "name"

    def test_function_without_return_type(self) -> None:
        """No return_type key when return_type is None."""
        from axm_ast.models.nodes import FunctionInfo

        fn = FunctionInfo(
            name="do_stuff",
            line_start=1,
            line_end=3,
            return_type=None,
            params=[],
            docstring=None,
        )
        detail = InspectTool._function_detail(fn, file="a.py")
        assert "return_type" not in detail


class TestClassDetail:
    """Tests for InspectTool._class_detail (extracted from _build_detail)."""

    def test_class_detail_methods(self) -> None:
        """_class_detail includes bases and methods list."""
        from axm_ast.models.nodes import ClassInfo, FunctionInfo

        method = FunctionInfo(
            name="run",
            line_start=10,
            line_end=12,
            return_type=None,
            params=[],
            docstring=None,
        )
        cls = ClassInfo(
            name="Runner",
            line_start=5,
            line_end=15,
            bases=["BaseRunner"],
            methods=[method],
            docstring="A runner.",
        )
        detail = InspectTool._class_detail(cls, file="run.py")
        assert detail["name"] == "Runner"
        assert detail["bases"] == ["BaseRunner"]
        assert "run" in detail["methods"]

    def test_class_without_bases_or_methods(self) -> None:
        """No bases/methods keys when lists are empty."""
        from axm_ast.models.nodes import ClassInfo

        cls = ClassInfo(
            name="Empty",
            line_start=1,
            line_end=2,
            bases=[],
            methods=[],
            docstring=None,
        )
        detail = InspectTool._class_detail(cls, file="a.py")
        assert "bases" not in detail
        assert "methods" not in detail


# ---------------------------------------------------------------------------
# Batch loop — _inspect_batch
# ---------------------------------------------------------------------------


class TestInspectBatch:
    """InspectTool._inspect_batch — extracted batch loop."""

    def test_collects_successful_symbols(self, tool: InspectTool) -> None:
        project_path = MagicMock()
        tool._inspect_symbol = MagicMock(  # type: ignore[method-assign]
            return_value=ToolResult(
                success=True,
                data={"symbol": {"name": "Foo", "kind": "class"}},
            )
        )
        result = tool._inspect_batch(project_path, ["Foo"], source=False)
        assert result.success
        assert len(result.data["symbols"]) == 1
        assert result.data["symbols"][0]["name"] == "Foo"

    def test_includes_error_entry_for_failed_lookup(self, tool: InspectTool) -> None:
        project_path = MagicMock()
        tool._inspect_symbol = MagicMock(  # type: ignore[method-assign]
            return_value=ToolResult(success=False, error="Symbol not found")
        )
        result = tool._inspect_batch(project_path, ["Missing"], source=False)
        assert result.success
        assert result.data["symbols"][0]["name"] == "Missing"
        assert result.data["symbols"][0]["error"] == "Symbol not found"

    def test_multiple_symbols_mixed_results(self, tool: InspectTool) -> None:
        project_path = MagicMock()
        ok = ToolResult(success=True, data={"symbol": {"name": "A", "kind": "class"}})
        err = ToolResult(success=False, error="not found")
        tool._inspect_symbol = MagicMock(side_effect=[ok, err])  # type: ignore[method-assign]
        result = tool._inspect_batch(project_path, ["A", "B"], source=False)
        assert result.success
        assert len(result.data["symbols"]) == 2
        assert result.data["symbols"][0]["name"] == "A"
        assert result.data["symbols"][1]["error"] == "not found"

    def test_non_list_returns_error(self, tool: InspectTool) -> None:
        result = tool._inspect_batch(MagicMock(), "not-a-list", source=False)
        assert not result.success
        assert result.error is not None
        assert "must be a list" in result.error


# ---------------------------------------------------------------------------
# Module resolution — _resolve_module
# ---------------------------------------------------------------------------


class TestResolveModule:
    """InspectTool._resolve_module — module name matching."""

    def test_exact_match_returns_module(
        self, tool: InspectTool, mock_pkg: MagicMock
    ) -> None:
        result = tool._resolve_module(mock_pkg, "pkg.alpha")
        assert result is not None
        assert not isinstance(result, ToolResult)

    def test_substring_unique_returns_module(
        self, tool: InspectTool, mock_pkg: MagicMock
    ) -> None:
        result = tool._resolve_module(mock_pkg, "beta")
        assert result is not None
        assert not isinstance(result, ToolResult)

    def test_substring_ambiguous_returns_error(
        self, tool: InspectTool, mock_pkg: MagicMock
    ) -> None:
        result = tool._resolve_module(mock_pkg, "alpha")
        assert isinstance(result, ToolResult)
        assert not result.success
        assert result.error is not None
        assert "Multiple modules" in result.error

    def test_no_match_returns_none(
        self, tool: InspectTool, mock_pkg: MagicMock
    ) -> None:
        result = tool._resolve_module(mock_pkg, "nonexistent")
        assert result is None
