"""Split from ``test_inspect.py``."""

from pathlib import Path

import pytest

from axm_ast.tools.inspect_detail import build_detail
from axm_ast.tools.inspect_resolve import find_symbol_file


class TestFindSymbolFile:
    """Tests for find_symbol_file."""

    @pytest.mark.parametrize(
        ("symbol_name", "expected_file"),
        [
            pytest.param("greet", "core.py", id="function"),
            pytest.param("MyClass", "core.py", id="class"),
            pytest.param("helper_func", "helpers.py", id="nested_function"),
        ],
    )
    def test_find_symbol_file(
        self,
        rich_pkg__from_inspect: Path,
        symbol_name: str,
        expected_file: str,
    ) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name=symbol_name)
        assert results
        file_path = find_symbol_file(pkg, results[0][1])
        assert expected_file in file_path


class TestBuildDetail:
    """Tests for build_detail."""

    def test_function_detail_keys(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        assert results
        detail = build_detail(results[0][1], file="core.py")
        assert detail["name"] == "greet"
        assert detail["file"] == "core.py"
        assert "start_line" in detail
        assert "end_line" in detail
        assert "signature" in detail

    def test_class_detail_has_methods(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols
        from axm_ast.models.nodes import ClassInfo

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="MyClass")
        cls = next(sym for _, sym in results if isinstance(sym, ClassInfo))
        detail = build_detail(cls, file="core.py")
        assert detail["name"] == "MyClass"
        assert "methods" in detail
        assert "my_method" in detail["methods"]

    def test_detail_without_source(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        detail = build_detail(results[0][1], file="core.py", source=False)
        assert "source" not in detail

    def test_detail_with_source(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        abs_path = str(rich_pkg__from_inspect / "core.py")
        detail = build_detail(
            results[0][1], file="core.py", abs_path=abs_path, source=True
        )
        assert "source" in detail
        assert "def greet" in detail["source"]
