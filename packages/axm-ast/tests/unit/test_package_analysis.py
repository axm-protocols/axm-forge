"""Integration tests for build_import_graph, search_symbols,
and find_module_for_symbol — internal boundary with real filesystem parsing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    analyze_package,
    build_import_graph,
    find_module_for_symbol,
    search_symbols,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    SymbolKind,
    VariableInfo,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── build_import_graph ─────────────────────────────────────────────────────


@pytest.mark.integration
class TestBuildImportGraph:
    """Tests for internal import graph construction."""

    def test_graph_contains_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
        graph = build_import_graph(pkg)
        assert len(graph) > 0, "Graph should contain at least one module"


# ─── search_symbols ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestSearchSymbols:
    """Tests for semantic search across a real package."""

    def test_search_by_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="greet")
        assert len(results) >= 1
        assert results[0][1].name == "greet"

    def test_search_by_return_type(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names

    def test_search_by_kind(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.PROPERTY)
        assert len(results) >= 1
        assert all(
            isinstance(sym, FunctionInfo) and sym.kind == FunctionKind.PROPERTY
            for _, sym in results
        )

    def test_search_by_kind_class(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.CLASS)
        assert len(results) >= 1
        assert all(isinstance(sym, ClassInfo) for _, sym in results)

    def test_search_by_kind_function(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.FUNCTION)
        assert len(results) >= 1
        assert all(
            isinstance(sym, FunctionInfo) and sym.kind == FunctionKind.FUNCTION
            for _, sym in results
        )
        names = [sym.name for _, sym in results]
        assert "Calculator" not in names

    def test_search_no_results(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="nonexistent_xyz")
        assert results == []

    def test_search_by_base_class(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, inherits="BaseModel")
        assert results == []

    def test_search_variable_by_name(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        assert len(results) >= 1
        match = [sym for _, sym in results if sym.name == "MAX_RETRIES"]
        assert len(match) == 1
        assert isinstance(match[0], VariableInfo)
        assert match[0].line > 0

    def test_search_variable_kind_filter(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.VARIABLE)
        assert len(results) >= 1
        assert all(isinstance(sym, VariableInfo) for _, sym in results)
        names = [sym.name for _, sym in results]
        assert "MAX_RETRIES" in names
        assert "DEFAULT_NAME" in names
        assert "greet" not in names
        assert "Calculator" not in names

    def test_search_kind_none_includes_variables(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "MAX_RETRIES" in names

    def test_search_annotated_variable(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        match = [sym for _, sym in results if sym.name == "MAX_RETRIES"]
        assert len(match) == 1
        var = match[0]
        assert isinstance(var, VariableInfo)
        assert var.annotation == "int"


# ─── find_module_for_symbol ─────────────────────────────────────────────────


@pytest.mark.integration
class TestFindModuleForSymbol:
    """Tests for find_module_for_symbol()."""

    def test_find_by_function_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "greet")
        assert mod is not None
        assert any(f.name == "greet" for f in mod.functions)

    def test_find_by_class_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "Calculator")
        assert mod is not None
        assert any(c.name == "Calculator" for c in mod.classes)

    def test_find_by_variable_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "MAX_RETRIES")
        assert mod is not None
        assert any(v.name == "MAX_RETRIES" for v in mod.variables)

    def test_find_by_object_identity(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="greet")
        assert len(results) >= 1
        _, func = results[0]
        mod = find_module_for_symbol(pkg, func)
        assert mod is not None
        assert any(f.name == "greet" for f in mod.functions)

    def test_find_unknown_returns_none(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert find_module_for_symbol(pkg, "nonexistent_xyz") is None
