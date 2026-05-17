"""Unit tests for axm_ast.core.analyzer — in-memory fixtures, no filesystem.

Covers: find_module_for_symbol, search_symbols (kind dispatch, return-type
filtering, module-name propagation, edge cases), module_dotted_name.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import (
    search_symbols,
)
from axm_ast.models.nodes import (
    PackageInfo,
)

# ────────────────────────────────────────────────────────────────────────
# search_symbols — name, return type, inheritance filters
# ────────────────────────────────────────────────────────────────────────


class TestSearchByName:
    def test_search_by_name(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, name="greet")
        assert len(results) >= 1
        assert any(sym.name == "greet" for _, sym in results)

    def test_substring_match(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, name="RETRI")
        assert any(sym.name == "MAX_RETRIES" for _, sym in results)


class TestSearchByReturnType:
    def test_filter_by_return_type(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "User" not in names

    def test_return_type_includes_methods(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, returns="bool")
        names = [sym.name for _, sym in results]
        assert "validate" in names or "is_valid" in names


class TestSearchInherits:
    def test_inherits_base_model(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="BaseModel")
        names = [sym.name for _, sym in results]
        assert "User" in names

    def test_inherits_user(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="User")
        names = [sym.name for _, sym in results]
        assert "Admin" in names

    def test_inherits_nonexistent(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="NonExistent")
        assert results == []


def test_returns_excludes_variables(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(rich_pkg__from_analyzer, returns="str")
    names = [sym.name for _, sym in results]
    assert "_PRIVATE" not in names
    assert "greet" in names


def test_returns_excludes_name_matched_classes(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer, name="User", returns="int")
    names = [sym.name for _, sym in results]
    assert "User" not in names


def test_no_returns_still_includes_variables(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer)
    names = [sym.name for _, sym in results]
    assert "_PRIVATE" in names


def test_name_match_no_returns_still_returns_class(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer, name="User")
    names = [sym.name for _, sym in results]
    assert "User" in names


def test_no_filters_returns_all(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(rich_pkg__from_analyzer)
    names = [sym.name for _, sym in results]
    assert "greet" in names
    assert "compute" in names
    assert "parse" in names
    assert "VERSION" in names


def test_empty_package() -> None:
    pkg = PackageInfo(name="empty", root=Path("empty"), modules=[])
    results = search_symbols(pkg)
    assert results == []
