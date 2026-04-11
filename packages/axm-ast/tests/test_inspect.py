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
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "core.py" in file_path

    def test_find_class_file(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="MyClass")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "core.py" in file_path

    def test_find_nested_function(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="helper_func")
        assert results
        file_path = InspectTool._find_symbol_file(pkg, results[0][1])
        assert "helpers.py" in file_path


# ─── _build_detail (unit) ────────────────────────────────────────────────────


class TestBuildDetail:
    """Tests for InspectTool._build_detail static method."""

    def test_function_detail_keys(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        assert results
        detail = InspectTool._build_detail(results[0][1], file="core.py")
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
        cls = next(sym for _, sym in results if isinstance(sym, ClassInfo))
        detail = InspectTool._build_detail(cls, file="core.py")
        assert detail["name"] == "MyClass"
        assert "methods" in detail
        assert "my_method" in detail["methods"]

    def test_detail_without_source(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        detail = InspectTool._build_detail(results[0][1], file="core.py", source=False)
        assert "source" not in detail

    def test_detail_with_source(self, rich_pkg: Path) -> None:
        from axm_ast.core.analyzer import analyze_package, search_symbols

        pkg = analyze_package(rich_pkg)
        results = search_symbols(pkg, name="greet")
        abs_path = str(rich_pkg / "core.py")
        detail = InspectTool._build_detail(
            results[0][1], file="core.py", abs_path=abs_path, source=True
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

    def test_symbols_invalid_type(self, tool: InspectTool) -> None:
        result = tool.execute(path=".", symbols="not_a_list")  # type: ignore
        assert result.success is False
        assert result.error is not None
        assert "must be a list" in result.error

    def test_symbols_batch_success(self, tool: InspectTool, rich_pkg: Path) -> None:
        result = tool.execute(path=str(rich_pkg), symbols=["greet", "MyClass"])
        assert result.success is True
        assert "symbols" in result.data
        symbols = result.data["symbols"]
        assert len(symbols) == 2
        assert symbols[0]["name"] == "greet"
        assert symbols[1]["name"] == "MyClass"

    def test_symbols_batch_partial_missing(
        self, tool: InspectTool, rich_pkg: Path
    ) -> None:
        result = tool.execute(
            path=str(rich_pkg), symbols=["greet", "missing_xyz", "core"]
        )
        assert result.success is True
        symbols = result.data["symbols"]
        assert len(symbols) == 3

        # 0: greet (success)
        assert symbols[0]["name"] == "greet"
        assert "signature" in symbols[0]

        # 1: missing_xyz (error)
        assert symbols[1]["name"] == "missing_xyz"
        assert "error" in symbols[1]
        assert "not found" in symbols[1]["error"]

        # 2: core (module fallback success)
        assert symbols[2]["name"] == "core"
        assert symbols[2]["kind"] == "module"

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


# ─── Module fallback ─────────────────────────────────────────────────────────


class TestInspectModuleFallback:
    """Tests for module fallback when symbol not found (AXM-430)."""

    def test_inspect_module_by_name(self, tool: InspectTool, rich_pkg: Path) -> None:
        """AC1: ast_inspect(symbol='core') returns module metadata."""
        result = tool.execute(path=str(rich_pkg), symbol="core")
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["kind"] == "module"
        assert "functions" in sym
        assert "classes" in sym
        assert "symbol_count" in sym

    def test_inspect_module_has_file(self, tool: InspectTool, rich_pkg: Path) -> None:
        """AC2: Module metadata includes a valid relative file path."""
        result = tool.execute(path=str(rich_pkg), symbol="core")
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["file"]
        assert "core.py" in sym["file"]

    def test_inspect_module_has_docstring(
        self, tool: InspectTool, rich_pkg: Path
    ) -> None:
        """AC2: Module metadata includes docstring when present."""
        result = tool.execute(path=str(rich_pkg), symbol="core")
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["docstring"] == "Core module."

    def test_inspect_symbol_still_preferred(
        self, tool: InspectTool, rich_pkg: Path
    ) -> None:
        """AC3: Symbol match takes priority over module fallback."""
        result = tool.execute(path=str(rich_pkg), symbol="greet")
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["name"] == "greet"
        assert sym.get("kind") != "module"
        assert "signature" in sym

    def test_no_match_still_errors(self, tool: InspectTool, rich_pkg: Path) -> None:
        """Edge: No symbol and no module → error."""
        result = tool.execute(path=str(rich_pkg), symbol="zzz_nonexistent")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error

    def test_inspect_nested_module(self, tool: InspectTool, rich_pkg: Path) -> None:
        """Module fallback works for nested modules via dotted name."""
        result = tool.execute(path=str(rich_pkg), symbol="sub.helpers")
        assert result.success is True
        sym = result.data["symbol"]
        assert sym["kind"] == "module"
        assert "helper_func" in sym["functions"]


# ─── _build_detail extracted helpers (unit) ──────────────────────────────────


class TestVariableDetail:
    """Tests for InspectTool._variable_detail (extracted from _build_detail)."""

    def test_variable_detail_keys(self) -> None:
        """_variable_detail returns dict with expected keys."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="MY_CONST", line=10, annotation="int", value_repr="42")
        detail = InspectTool._variable_detail(var, file="mod.py")
        assert detail["name"] == "MY_CONST"
        assert detail["file"] == "mod.py"
        assert detail["kind"] == "variable"
        assert detail["start_line"] == 10
        assert detail["end_line"] == 10
        assert detail["module"] == ""

    def test_variable_without_annotation(self) -> None:
        """No annotation key when annotation is None."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="x", line=1, annotation=None, value_repr="1")
        detail = InspectTool._variable_detail(var, file="a.py")
        assert "annotation" not in detail

    def test_variable_with_annotation(self) -> None:
        """Annotation key present when set."""
        from axm_ast.models.nodes import VariableInfo

        var = VariableInfo(name="x", line=1, annotation="str", value_repr=None)
        detail = InspectTool._variable_detail(var, file="a.py")
        assert detail["annotation"] == "str"


class TestFunctionDetail:
    """Tests for InspectTool._function_detail (extracted from _build_detail)."""

    def test_function_detail_params(self) -> None:
        """_function_detail includes signature and parameters list."""
        from axm_ast.models.nodes import FunctionInfo, ParameterInfo

        fn = FunctionInfo(
            name="greet",
            line_start=5,
            line_end=8,
            return_type="str",
            params=[ParameterInfo(name="name", annotation="str", default=None)],
            docstring="Say hello.",
        )
        detail = InspectTool._function_detail(fn, file="core.py")
        assert detail["name"] == "greet"
        assert detail["signature"] == "def greet(name: str) -> str"
        assert len(detail["parameters"]) == 1
        assert detail["parameters"][0]["name"] == "name"

    def test_function_without_return_type(self) -> None:
        """No return_type key when return_type is None."""
        from axm_ast.models.nodes import FunctionInfo

        fn = FunctionInfo(
            name="do_stuff",
            line_start=1,
            line_end=3,
            return_type=None,
            params=[],
            docstring=None,
        )
        detail = InspectTool._function_detail(fn, file="a.py")
        assert "return_type" not in detail


class TestClassDetail:
    """Tests for InspectTool._class_detail (extracted from _build_detail)."""

    def test_class_detail_methods(self) -> None:
        """_class_detail includes bases and methods list."""
        from axm_ast.models.nodes import ClassInfo, FunctionInfo

        method = FunctionInfo(
            name="run",
            line_start=10,
            line_end=12,
            return_type=None,
            params=[],
            docstring=None,
        )
        cls = ClassInfo(
            name="Runner",
            line_start=5,
            line_end=15,
            bases=["BaseRunner"],
            methods=[method],
            docstring="A runner.",
        )
        detail = InspectTool._class_detail(cls, file="run.py")
        assert detail["name"] == "Runner"
        assert detail["bases"] == ["BaseRunner"]
        assert "run" in detail["methods"]

    def test_class_without_bases_or_methods(self) -> None:
        """No bases/methods keys when lists are empty."""
        from axm_ast.models.nodes import ClassInfo

        cls = ClassInfo(
            name="Empty",
            line_start=1,
            line_end=2,
            bases=[],
            methods=[],
            docstring=None,
        )
        detail = InspectTool._class_detail(cls, file="a.py")
        assert "bases" not in detail
        assert "methods" not in detail
