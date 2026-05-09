"""Unit tests for InspectTool — no real I/O."""

from __future__ import annotations

import pytest

from axm_ast.tools.inspect import InspectTool


@pytest.fixture()
def tool() -> InspectTool:
    """Provide a fresh InspectTool instance."""
    return InspectTool()


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
