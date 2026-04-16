"""Unit tests for SearchTool._format_symbol — module name propagation."""

from __future__ import annotations

import pytest

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    VariableInfo,
)
from axm_ast.tools.search import SearchTool


@pytest.fixture()
def function_symbol() -> FunctionInfo:
    return FunctionInfo(
        name="greet",
        signature="(name: str) -> str",
        return_type="str",
        kind=FunctionKind.FUNCTION,
        line_start=5,
        line_end=7,
        decorators=[],
    )


@pytest.fixture()
def class_symbol() -> ClassInfo:
    return ClassInfo(
        name="Greeter",
        bases=["object"],
        line_start=10,
        line_end=20,
        decorators=[],
        methods=[],
    )


@pytest.fixture()
def variable_symbol() -> VariableInfo:
    return VariableInfo(
        name="VERSION",
        line=1,
        annotation="str",
        value_repr='"1.0"',
    )


class TestFormatSymbolModuleName:
    """_format_symbol must receive and include the module name."""

    def test_format_symbol_includes_module_name(
        self, function_symbol: FunctionInfo
    ) -> None:
        entry = SearchTool._format_symbol(function_symbol, "pkg.utils")
        assert entry["module"] == "pkg.utils"

    def test_format_symbol_module_never_empty(
        self,
        function_symbol: FunctionInfo,
        class_symbol: ClassInfo,
        variable_symbol: VariableInfo,
    ) -> None:
        symbols: list[tuple[FunctionInfo | ClassInfo | VariableInfo, str]] = [
            (function_symbol, "pkg.funcs"),
            (class_symbol, "pkg.classes"),
            (variable_symbol, "pkg.consts"),
        ]
        for sym, mod_name in symbols:
            entry = SearchTool._format_symbol(sym, mod_name)
            assert entry["module"] != "", f"module empty for {sym.name}"
            assert entry["module"] == mod_name
