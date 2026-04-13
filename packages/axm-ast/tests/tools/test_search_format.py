from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.search import SearchTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def function_sym() -> dict[str, Any]:
    return {
        "name": "do_work",
        "kind": "function",
        "signature": "def do_work(a: int, b: str) -> bool",
        "return_type": "bool",
    }


@pytest.fixture()
def class_sym() -> dict[str, Any]:
    return {"name": "MyClass", "kind": "class"}


@pytest.fixture()
def variable_sym_annotated() -> dict[str, Any]:
    return {
        "name": "timeout",
        "kind": "variable",
        "annotation": "int",
        "value_repr": "30",
    }


# ---------------------------------------------------------------------------
# Unit tests — _format_symbol_line
# ---------------------------------------------------------------------------


def test_format_symbol_line_function(function_sym: dict[str, Any]) -> None:
    result = SearchTool._format_symbol_line(function_sym)
    assert result == "do_work(a: int, b: str) -> bool"


def test_format_symbol_line_class(class_sym: dict[str, Any]) -> None:
    result = SearchTool._format_symbol_line(class_sym)
    assert result == "MyClass"


def test_format_symbol_line_variable_annotated(
    variable_sym_annotated: dict[str, Any],
) -> None:
    result = SearchTool._format_symbol_line(variable_sym_annotated)
    assert result == "timeout: int = 30"


# ---------------------------------------------------------------------------
# Unit test — _format_symbol (dict output from AST objects)
# ---------------------------------------------------------------------------


def test_format_symbol_dict() -> None:
    from axm_ast.models.nodes import ClassInfo, FunctionInfo, VariableInfo

    # FunctionInfo
    func = MagicMock(spec=FunctionInfo)
    func.name = "run"
    func.signature = "def run(self) -> None"
    func.return_type = "None"
    func.kind = MagicMock()
    func.kind.value = "method"
    result_func = SearchTool._format_symbol(func, "my_module")
    assert result_func["name"] == "run"
    assert result_func["module"] == "my_module"
    assert result_func["signature"] == "def run(self) -> None"
    assert result_func["return_type"] == "None"
    assert result_func["kind"] == "method"

    # ClassInfo
    cls = MagicMock(spec=ClassInfo)
    cls.name = "Widget"
    result_cls = SearchTool._format_symbol(cls, "widgets")
    assert result_cls["name"] == "Widget"
    assert result_cls["kind"] == "class"

    # VariableInfo
    var = MagicMock(spec=VariableInfo)
    var.name = "MAX"
    var.annotation = "int"
    var.value_repr = "100"
    result_var = SearchTool._format_symbol(var, "constants")
    assert result_var["name"] == "MAX"
    assert result_var["kind"] == "variable"
    assert result_var["annotation"] == "int"
    assert result_var["value_repr"] == "100"


# ---------------------------------------------------------------------------
# Unit test — _render_text
# ---------------------------------------------------------------------------


def test_render_text_mixed(
    function_sym: dict[str, Any],
    class_sym: dict[str, Any],
    variable_sym_annotated: dict[str, Any],
) -> None:
    symbols = [function_sym, class_sym, variable_sym_annotated]
    result = SearchTool._render_text(
        symbols, name=None, returns=None, kind=None, inherits=None
    )
    lines = result.split("\n")
    # First line is the header
    assert "3 hits" in lines[0]
    # Functions appear before classes, classes before variables
    func_idx = next(i for i, line in enumerate(lines) if "do_work" in line)
    cls_idx = next(i for i, line in enumerate(lines) if "MyClass" in line)
    var_idx = next(i for i, line in enumerate(lines) if "timeout" in line)
    assert func_idx < cls_idx < var_idx


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_format_symbol_line_no_params_in_signature() -> None:
    """Signature without parentheses falls back to ()."""
    sym: dict[str, Any] = {
        "name": "ping",
        "kind": "function",
        "signature": "def ping",
        "return_type": None,
    }
    result = SearchTool._format_symbol_line(sym)
    assert result == "ping()"


def test_format_symbol_line_nested_parens() -> None:
    """Nested parens in type hints are matched correctly."""
    sym: dict[str, Any] = {
        "name": "f",
        "kind": "function",
        "signature": "def f(x: dict[str, list[int]])",
        "return_type": None,
    }
    result = SearchTool._format_symbol_line(sym)
    assert result == "f(x: dict[str, list[int]])"


def test_format_symbol_line_variable_bare() -> None:
    """Variable with no annotation or value returns just the name."""
    sym: dict[str, Any] = {"name": "flag", "kind": "variable"}
    result = SearchTool._format_symbol_line(sym)
    assert result == "flag"
