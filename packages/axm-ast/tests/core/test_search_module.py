"""Tests for _search_module — unit, functional, and edge-case coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    _search_module,
    search_symbols,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
    SymbolKind,
    VariableInfo,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def mod_with_variables() -> ModuleInfo:
    """Module containing only variables."""
    return ModuleInfo(
        path=Path("vars.py"),
        variables=[
            VariableInfo(name="MAX_RETRIES", annotation="int", value_repr="3", line=1),
            VariableInfo(name="TIMEOUT", annotation="float", value_repr="30.0", line=2),
            VariableInfo(name="_PRIVATE", annotation=None, value_repr="True", line=3),
        ],
    )


@pytest.fixture()
def mod_with_classes() -> ModuleInfo:
    """Module containing only classes."""
    return ModuleInfo(
        path=Path("models.py"),
        classes=[
            ClassInfo(
                name="User",
                bases=["BaseModel"],
                line_start=1,
                line_end=10,
                methods=[
                    FunctionInfo(
                        name="validate",
                        kind=FunctionKind.METHOD,
                        return_type="bool",
                        line_start=5,
                        line_end=8,
                    ),
                ],
            ),
            ClassInfo(
                name="Admin",
                bases=["User"],
                line_start=12,
                line_end=20,
            ),
        ],
    )


@pytest.fixture()
def mod_mixed() -> ModuleInfo:
    """Module with top-level functions, classes with methods, and variables."""
    return ModuleInfo(
        path=Path("mixed.py"),
        functions=[
            FunctionInfo(
                name="greet",
                kind=FunctionKind.FUNCTION,
                return_type="str",
                line_start=1,
                line_end=3,
            ),
            FunctionInfo(
                name="compute",
                kind=FunctionKind.FUNCTION,
                return_type="int",
                line_start=5,
                line_end=7,
            ),
        ],
        classes=[
            ClassInfo(
                name="Parser",
                bases=[],
                line_start=10,
                line_end=30,
                methods=[
                    FunctionInfo(
                        name="parse",
                        kind=FunctionKind.METHOD,
                        return_type="str",
                        line_start=12,
                        line_end=15,
                    ),
                    FunctionInfo(
                        name="is_valid",
                        kind=FunctionKind.PROPERTY,
                        return_type="bool",
                        line_start=17,
                        line_end=20,
                    ),
                ],
            ),
        ],
        variables=[
            VariableInfo(name="VERSION", annotation="str", value_repr='"1.0"', line=35),
        ],
    )


@pytest.fixture()
def rich_pkg(
    mod_with_variables: ModuleInfo,
    mod_with_classes: ModuleInfo,
    mod_mixed: ModuleInfo,
) -> PackageInfo:
    """Package combining all test modules."""
    return PackageInfo(
        name="demo",
        root=Path("src/demo"),
        modules=[mod_with_variables, mod_with_classes, mod_mixed],
    )


# ─── Unit tests — _search_module ─────────────────────────────────────────────


class TestSearchVariableKind:
    """kind=VARIABLE returns only VariableInfo."""

    def test_returns_only_variables(self, mod_mixed: ModuleInfo) -> None:
        results = _search_module(
            mod_mixed,
            name=None,
            returns=None,
            kind=SymbolKind.VARIABLE,
            inherits=None,
        )
        assert len(results) == 1
        assert all(isinstance(r, VariableInfo) for r in results)
        assert results[0].name == "VERSION"

    def test_variable_kind_with_name_filter(
        self, mod_with_variables: ModuleInfo
    ) -> None:
        results = _search_module(
            mod_with_variables,
            name="TIMEOUT",
            returns=None,
            kind=SymbolKind.VARIABLE,
            inherits=None,
        )
        assert len(results) == 1
        assert results[0].name == "TIMEOUT"


class TestSearchClassKind:
    """kind=CLASS returns only ClassInfo."""

    def test_returns_only_classes(self, mod_with_classes: ModuleInfo) -> None:
        results = _search_module(
            mod_with_classes,
            name=None,
            returns=None,
            kind=SymbolKind.CLASS,
            inherits=None,
        )
        assert len(results) == 2
        assert all(isinstance(r, ClassInfo) for r in results)
        names = [r.name for r in results]
        assert "User" in names
        assert "Admin" in names

    def test_class_kind_with_name_filter(self, mod_with_classes: ModuleInfo) -> None:
        results = _search_module(
            mod_with_classes,
            name="Admin",
            returns=None,
            kind=SymbolKind.CLASS,
            inherits=None,
        )
        assert len(results) == 1
        assert results[0].name == "Admin"


class TestSearchFunctionKind:
    """kind=FUNCTION/METHOD/PROPERTY dispatch to class methods."""

    def test_returns_top_level_functions(self, mod_mixed: ModuleInfo) -> None:
        results = _search_module(
            mod_mixed,
            name=None,
            returns=None,
            kind=SymbolKind.FUNCTION,
            inherits=None,
        )
        assert all(isinstance(r, FunctionInfo) for r in results)
        names = [r.name for r in results]
        assert "greet" in names
        assert "compute" in names
        assert "Parser" not in names
        assert "VERSION" not in names

    def test_method_kind_returns_methods(self, mod_mixed: ModuleInfo) -> None:
        results = _search_module(
            mod_mixed,
            name=None,
            returns=None,
            kind=SymbolKind.METHOD,
            inherits=None,
        )
        assert all(isinstance(r, FunctionInfo) for r in results)
        names = [r.name for r in results]
        assert "parse" in names
        assert "greet" not in names

    def test_property_kind_returns_properties(self, mod_mixed: ModuleInfo) -> None:
        results = _search_module(
            mod_mixed,
            name=None,
            returns=None,
            kind=SymbolKind.PROPERTY,
            inherits=None,
        )
        names = [r.name for r in results]
        assert "is_valid" in names
        assert "parse" not in names


# ─── Functional / regression tests — search_symbols ─────────────────────────


class TestSearchByName:
    """Name-based search returns correct symbols."""

    def test_search_by_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, name="greet")
        assert len(results) >= 1
        assert any(sym.name == "greet" for _, sym in results)

    def test_substring_match(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, name="RETRI")
        assert any(sym.name == "MAX_RETRIES" for _, sym in results)


class TestSearchByReturnType:
    """Return type filter works correctly."""

    def test_filter_by_return_type(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names
        # Classes without return type excluded
        assert "User" not in names

    def test_return_type_includes_methods(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, returns="bool")
        names = [sym.name for _, sym in results]
        assert "validate" in names or "is_valid" in names


class TestSearchByKindAndName:
    """Combined kind + name filters work."""

    def test_function_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.FUNCTION, name="greet")
        assert len(results) == 1
        assert results[0][1].name == "greet"

    def test_class_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.CLASS, name="User")
        assert len(results) == 1
        assert results[0][1].name == "User"

    def test_variable_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.VARIABLE, name="TIMEOUT")
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


class TestSearchInherits:
    """Inheritance search is delegated correctly."""

    def test_inherits_base_model(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="BaseModel")
        names = [sym.name for _, sym in results]
        assert "User" in names

    def test_inherits_user(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="User")
        names = [sym.name for _, sym in results]
        assert "Admin" in names

    def test_inherits_nonexistent(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="NonExistent")
        assert results == []


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Boundary conditions for _search_module."""

    def test_variable_kind_with_returns_empty(
        self, mod_with_variables: ModuleInfo
    ) -> None:
        """kind=VARIABLE + returns set → empty (variables have no return type)."""
        results = _search_module(
            mod_with_variables,
            name=None,
            returns="str",
            kind=SymbolKind.VARIABLE,
            inherits=None,
        )
        assert results == []

    def test_class_kind_with_returns_empty(self, mod_with_classes: ModuleInfo) -> None:
        """kind=CLASS + returns set → empty (classes have no return type)."""
        results = _search_module(
            mod_with_classes,
            name=None,
            returns="int",
            kind=SymbolKind.CLASS,
            inherits=None,
        )
        assert results == []

    def test_no_filters_returns_all(self, mod_mixed: ModuleInfo) -> None:
        """kind=None + no name → all functions + classes + variables."""
        results = _search_module(
            mod_mixed,
            name=None,
            returns=None,
            kind=None,
            inherits=None,
        )
        names = [r.name for r in results]
        assert "greet" in names
        assert "compute" in names
        # _search_classes with name=None returns methods, not the class itself
        assert "parse" in names
        assert "VERSION" in names

    def test_empty_module(self) -> None:
        """Empty module returns empty list."""
        mod = ModuleInfo(path=Path("empty.py"))
        results = _search_module(mod, name=None, returns=None, kind=None, inherits=None)
        assert results == []
