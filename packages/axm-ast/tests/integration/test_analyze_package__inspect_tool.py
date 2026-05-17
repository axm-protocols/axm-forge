"""Split from ``test_inspect.py``."""

from pathlib import Path

from axm_ast.tools.inspect import InspectTool


class TestFindSymbolFile:
    """Tests for InspectTool._find_symbol_file static method."""

    def test_find_function_file(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "core.py" in file_path

    def test_find_class_file(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="MyClass")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "core.py" in file_path

    def test_find_nested_function(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="helper_func")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "helpers.py" in file_path


class TestBuildDetail:
    """Tests for InspectTool._build_detail static method."""

    def test_function_detail_keys(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        assert results
        detail = InspectTool._build_detail(results[0][1], file="core.py")
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
        detail = InspectTool._build_detail(cls, file="core.py")
        assert detail["name"] == "MyClass"
        assert "methods" in detail
        assert "my_method" in detail["methods"]

    def test_detail_without_source(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        detail = InspectTool._build_detail(results[0][1], file="core.py", source=False)
        assert "source" not in detail

    def test_detail_with_source(self, rich_pkg__from_inspect: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg__from_inspect)
        results = search_symbols(pkg, name="greet")
        abs_path = str(rich_pkg__from_inspect / "core.py")
        detail = InspectTool._build_detail(
            results[0][1], file="core.py", abs_path=abs_path, source=True
        )
        assert "source" in detail
        assert "def greet" in detail["source"]
