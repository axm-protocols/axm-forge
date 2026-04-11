from __future__ import annotations

import pytest

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)

"""Tests for module name propagation in search results (AXM-1313)."""

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_module(
    name: str,
    *,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    variables: list[VariableInfo] | None = None,
) -> ModuleInfo:
    from pathlib import Path

    return ModuleInfo(
        name=name,
        path=Path(f"{name.replace('.', '/')}.py"),
        imports=[],
        functions=functions or [],
        classes=classes or [],
        variables=variables or [],
    )


def _make_package(*modules: ModuleInfo) -> PackageInfo:
    from pathlib import Path

    return PackageInfo(
        name="pkg",
        root=Path("/tmp/pkg"),
        modules=list(modules),
    )


# ---------------------------------------------------------------------------
# Unit tests — _format_symbol
# ---------------------------------------------------------------------------


class TestFormatSymbolModuleName:
    """_format_symbol must receive and include the module name."""

    def test_format_symbol_includes_module_name(
        self, function_symbol: FunctionInfo
    ) -> None:
        from axm_ast.tools.search import SearchTool

        entry = SearchTool._format_symbol(function_symbol, "pkg.utils")
        assert entry["module"] == "pkg.utils"

    def test_format_symbol_module_never_empty(
        self,
        function_symbol: FunctionInfo,
        class_symbol: ClassInfo,
        variable_symbol: VariableInfo,
    ) -> None:
        from axm_ast.tools.search import SearchTool

        symbols: list[tuple[FunctionInfo | ClassInfo | VariableInfo, str]] = [
            (function_symbol, "pkg.funcs"),
            (class_symbol, "pkg.classes"),
            (variable_symbol, "pkg.consts"),
        ]
        for sym, mod_name in symbols:
            entry = SearchTool._format_symbol(sym, mod_name)
            assert entry["module"] != "", f"module empty for {sym.name}"
            assert entry["module"] == mod_name


# ---------------------------------------------------------------------------
# Functional tests — search_symbols end-to-end
# ---------------------------------------------------------------------------


class TestSearchResultsModuleField:
    """search_symbols results must carry the originating module name."""

    def test_search_results_carry_module(
        self, function_symbol: FunctionInfo, class_symbol: ClassInfo
    ) -> None:
        from axm_ast.core.analyzer import search_symbols

        mod_a = _make_module("pkg.alpha", functions=[function_symbol])
        mod_b = _make_module("pkg.beta", classes=[class_symbol])
        pkg = _make_package(mod_a, mod_b)

        fn_results = search_symbols(pkg, name="greet")
        assert len(fn_results) == 1
        mod_name, sym = fn_results[0]
        assert mod_name == "pkg.alpha"
        assert sym.name == "greet"

        cls_results = search_symbols(pkg, name="Greeter")
        assert len(cls_results) == 1
        mod_name, sym = cls_results[0]
        assert mod_name == "pkg.beta"
        assert sym.name == "Greeter"

    def test_search_variable_has_module(self, variable_symbol: VariableInfo) -> None:
        from axm_ast.core.analyzer import search_symbols

        mod = _make_module("pkg.consts", variables=[variable_symbol])
        pkg = _make_package(mod)

        results = search_symbols(pkg, name="VERSION")

        assert len(results) == 1
        mod_name, matched = results[0]
        assert mod_name != ""
        assert mod_name == "pkg.consts"
        assert matched.name == "VERSION"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSearchModuleEdgeCases:
    """Edge cases for module name propagation."""

    def test_single_module_package_init(self, function_symbol: FunctionInfo) -> None:
        """Package with only __init__.py uses the init module path."""
        from axm_ast.core.analyzer import search_symbols

        mod = _make_module("pkg.__init__", functions=[function_symbol])
        pkg = _make_package(mod)

        results = search_symbols(pkg, name="greet")

        assert len(results) == 1
        mod_name, _sym = results[0]
        assert mod_name == "pkg.__init__"

    def test_nested_subpackage_module(self, class_symbol: ClassInfo) -> None:
        """Symbol in nested sub-package carries full dotted path."""
        from axm_ast.core.analyzer import search_symbols

        mod = _make_module("pkg.sub.mod", classes=[class_symbol])
        pkg = _make_package(mod)

        results = search_symbols(pkg, name="Greeter")

        assert len(results) == 1
        mod_name, _sym = results[0]
        assert mod_name == "pkg.sub.mod"
