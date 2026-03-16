"""Tests for InspectTool — symbol inspection by name."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.inspect import InspectTool

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


@pytest.fixture()
def tool() -> InspectTool:
    """Provide a fresh InspectTool instance."""
    return InspectTool()


@pytest.fixture()
def rich_pkg(tmp_path: Path) -> Path:
    """Create a package with nested modules and classes for inspect tests."""
    pkg = tmp_path / "inspectdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Inspect demo."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        '__all__ = ["greet", "MyClass"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n\n\n'
        "class MyClass:\n"
        '    """A demo class."""\n\n'
        "    def my_method(self) -> None:\n"
        '        """Run method."""\n\n'
        "    @property\n"
        "    def label(self) -> str:\n"
        '        """Get label."""\n'
        '        return "label"\n'
    )
    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text('"""Sub package."""\n')
    (sub / "helpers.py").write_text(
        '"""Helper module."""\n\n\n'
        "def helper_func() -> int:\n"
        '    """Help."""\n'
        "    return 42\n"
    )
    return pkg


# ─── _find_module_for_symbol (unit) ──────────────────────────────────────────


class TestFindSymbolFile:
    """Tests for InspectTool._find_symbol_file static method."""

    def test_find_function_file(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0])
        assert "core.py" in file_path

    def test_find_class_file(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="MyClass")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0])
        assert "core.py" in file_path

    def test_find_nested_function(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="helper_func")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0])
        assert "helpers.py" in file_path


# ─── _build_detail (unit) ────────────────────────────────────────────────────


class TestBuildDetail:
    """Tests for InspectTool._build_detail static method."""

    def test_function_detail_keys(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        assert results
        detail = InspectTool._build_detail(results[0], file="core.py")
        assert detail["name"] == "greet"
        assert detail["file"] == "core.py"
        assert "start_line" in detail
        assert "end_line" in detail
        assert "signature" in detail

    def test_class_detail_has_methods(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols
        from axm_ast.models.nodes import ClassInfo

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="MyClass")
        cls = next(r for r in results if isinstance(r, ClassInfo))
        detail = InspectTool._build_detail(cls, file="core.py")
        assert detail["name"] == "MyClass"
        assert "methods" in detail
        assert "my_method" in detail["methods"]

    def test_detail_without_source(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        detail = InspectTool._build_detail(results[0], file="core.py", source=False)
        assert "source" not in detail

    def test_detail_with_source(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        abs_path = str(rich_pkg / "core.py")
        detail = InspectTool._build_detail(
            results[0], file="core.py", abs_path=abs_path, source=True
        )
        assert "source" in detail
        assert "def greet" in detail["source"]


# ─── Dotted path resolution ─────────────────────────────────────────────────


class TestDottedPathResolution:
    """Tests for dotted path resolution (module.symbol and Class.method)."""

    def test_dotted_module_function(self, tool: InspectTool, rich_pkg: Path) -> None:
        """core.greet → function greet in core module."""
        result = tool.execute(path=str(rich_pkg), symbol="core.greet")
        assert result.success is True
        assert result.data["symbol"]["name"] == "greet"

    def test_dotted_module_class(self, tool: InspectTool, rich_pkg: Path) -> None:
        """core.MyClass → class in core module."""
        result = tool.execute(path=str(rich_pkg), symbol="core.MyClass")
        assert result.success is True
        assert result.data["symbol"]["name"] == "MyClass"

    def test_dotted_class_method(self, tool: InspectTool, rich_pkg: Path) -> None:
        """MyClass.my_method → method in class."""
        result = tool.execute(path=str(rich_pkg), symbol="MyClass.my_method")
        assert result.success is True
        assert result.data["symbol"]["name"] == "my_method"

    def test_dotted_nested_module(self, tool: InspectTool, rich_pkg: Path) -> None:
        """sub.helpers.helper_func → function in nested module."""
        result = tool.execute(path=str(rich_pkg), symbol="sub.helpers.helper_func")
        assert result.success is True
        assert result.data["symbol"]["name"] == "helper_func"

    def test_dotted_not_found(self, tool: InspectTool, rich_pkg: Path) -> None:
        """Module found but symbol missing → error."""
        result = tool.execute(path=str(rich_pkg), symbol="core.nonexistent")
        assert result.success is False
        assert result.error is not None
        assert "nonexistent" in result.error

    def test_double_dotted_not_found(self, tool: InspectTool, rich_pkg: Path) -> None:
        """Neither module nor class match → combined error."""
        result = tool.execute(path=str(rich_pkg), symbol="fake.module.xyz")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestInspectEdgeCases:
    """Edge cases for InspectTool."""

    def test_missing_symbol_param(self, tool: InspectTool) -> None:
        result = tool.execute(path=".")
        assert result.success is False
        assert result.error is not None
        assert "required" in result.error

    def test_bad_path(self, tool: InspectTool) -> None:
        result = tool.execute(path="/nonexistent/path", symbol="foo")
        assert result.success is False

    def test_symbol_not_found(self, tool: InspectTool, rich_pkg: Path) -> None:
        result = tool.execute(path=str(rich_pkg), symbol="totally_missing_xyz")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    def test_empty_package(self, tool: InspectTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        result = tool.execute(path=str(pkg), symbol="anything")
        assert result.success is False
