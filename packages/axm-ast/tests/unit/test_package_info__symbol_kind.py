"""Split from ``test_analyzer.py``."""

from axm_ast.core.analyzer import search_symbols
from axm_ast.models.nodes import (
    PackageInfo,
    SymbolKind,
)


def test_variable_kind_with_returns_empty(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(
        rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, returns="str"
    )
    assert results == []


def test_class_kind_with_returns_empty(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(
        rich_pkg__from_analyzer, kind=SymbolKind.CLASS, returns="int"
    )
    assert results == []


class TestSearchVariableKind:
    def test_returns_only_variables(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE)
        names = [sym.name for _, sym in results]
        assert "VERSION" in names
        assert "MAX_RETRIES" in names
        assert "greet" not in names
        assert "User" not in names

    def test_variable_kind_with_name_filter(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, name="TIMEOUT"
        )
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


class TestSearchClassKind:
    def test_returns_only_classes(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.CLASS)
        names = [sym.name for _, sym in results]
        assert "User" in names
        assert "Admin" in names
        assert "greet" not in names
        assert "VERSION" not in names

    def test_class_kind_with_name_filter(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.CLASS, name="Admin"
        )
        assert len(results) == 1
        assert results[0][1].name == "Admin"


class TestSearchFunctionKind:
    def test_returns_top_level_functions(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.FUNCTION)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "compute" in names
        assert "Parser" not in names
        assert "VERSION" not in names

    def test_method_kind_returns_methods(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.METHOD)
        names = [sym.name for _, sym in results]
        assert "parse" in names
        assert "greet" not in names

    def test_property_kind_returns_properties(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.PROPERTY)
        names = [sym.name for _, sym in results]
        assert "is_valid" in names
        assert "parse" not in names


class TestSearchByKindAndName:
    def test_function_kind_with_name(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.FUNCTION, name="greet"
        )
        assert len(results) == 1
        assert results[0][1].name == "greet"

    def test_class_kind_with_name(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.CLASS, name="User"
        )
        assert len(results) == 1
        assert results[0][1].name == "User"

    def test_variable_kind_with_name(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, name="TIMEOUT"
        )
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"
