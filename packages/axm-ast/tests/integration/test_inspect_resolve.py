from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.models import ClassInfo, FunctionInfo, ModuleInfo, PackageInfo


@pytest.fixture
def _fake_pkg() -> PackageInfo:
    """Build a minimal PackageInfo with modules and symbols."""
    method = FunctionInfo(
        name="do_stuff",
        line_start=10,
        line_end=15,
        signature="(self) -> None",
        params=[],
        return_type="None",
        docstring="method doc",
    )
    cls = ClassInfo(
        name="MyClass",
        line_start=5,
        line_end=20,
        docstring="class doc",
        bases=["Base"],
        methods=[method],
    )
    func = FunctionInfo(
        name="helper",
        line_start=25,
        line_end=30,
        signature="(x: int) -> str",
        params=[],
        return_type="str",
        docstring="helper doc",
    )
    from pathlib import Path

    mod = ModuleInfo(
        path=Path("/fake/src/mypkg/core.py"),
        name="core",
        docstring="core module",
        functions=[func],
        classes=[cls],
        variables=[],
        imports=[],
    )
    mod2 = ModuleInfo(
        path=Path("/fake/src/mypkg/sub/helpers.py"),
        name="sub.helpers",
        docstring="helpers module",
        functions=[],
        classes=[],
        variables=[],
        imports=[],
    )
    pkg = MagicMock(spec=PackageInfo)
    pkg.modules = [mod, mod2]
    pkg.module_names = ["core", "sub.helpers"]
    pkg.root = Path("/fake/src/mypkg")
    return pkg


class TestFindSymbolFile:
    """Verify symbol-to-file resolution after extraction."""

    def test_find_symbol_file_returns_relative_path(
        self, _fake_pkg: PackageInfo
    ) -> None:
        """_find_symbol_file returns a path relative to pkg root parent."""
        from axm_ast.tools.inspect_resolve import find_symbol_file

        cls = _fake_pkg.modules[0].classes[0]
        # Patch find_module_for_symbol to return our module
        import axm_ast.tools.inspect_resolve as mod

        original = mod.find_module_for_symbol
        mod.find_module_for_symbol = lambda pkg, sym: _fake_pkg.modules[0]  # type: ignore[assignment]
        try:
            result = find_symbol_file(_fake_pkg, cls)
            assert result == "mypkg/core.py"
        finally:
            mod.find_module_for_symbol = original

    def test_find_symbol_file_returns_empty_when_not_found(
        self, _fake_pkg: PackageInfo
    ) -> None:
        """Returns empty string when symbol module not found."""
        from axm_ast.tools.inspect_resolve import find_symbol_file

        cls = _fake_pkg.modules[0].classes[0]
        import axm_ast.tools.inspect_resolve as mod

        original = mod.find_module_for_symbol
        mod.find_module_for_symbol = lambda pkg, sym: None  # type: ignore[assignment]
        try:
            result = find_symbol_file(_fake_pkg, cls)
            assert result == ""
        finally:
            mod.find_module_for_symbol = original

    def test_resolve_module_exact_match(self, _fake_pkg: PackageInfo) -> None:
        """resolve_module finds exact module name."""
        from axm_ast.tools.inspect_resolve import resolve_module

        result = resolve_module(_fake_pkg, "core")
        assert result is not None
        assert not hasattr(result, "success")  # Not a ToolResult
        assert result.name == "core"

    def test_resolve_module_substring_match(self, _fake_pkg: PackageInfo) -> None:
        """resolve_module finds module by substring when unique."""
        from axm_ast.tools.inspect_resolve import resolve_module

        result = resolve_module(_fake_pkg, "sub.helpers")
        assert result is not None
        assert not hasattr(result, "success")
        assert result.name == "sub.helpers"

    def test_resolve_module_returns_none_on_miss(self, _fake_pkg: PackageInfo) -> None:
        """resolve_module returns None when no match."""
        from axm_ast.tools.inspect_resolve import resolve_module

        result = resolve_module(_fake_pkg, "nonexistent")
        assert result is None


class TestDottedPathResolution:
    """Verify Class.method style symbol delegation."""

    def test_resolve_class_method(self, _fake_pkg: PackageInfo) -> None:
        """resolve_class_method finds MyClass.do_stuff."""
        import axm_ast.tools.inspect_resolve as mod
        from axm_ast.tools.inspect_resolve import resolve_class_method

        # Patch search_symbols to return our class
        cls = _fake_pkg.modules[0].classes[0]
        original_search = mod.search_symbols
        mod.search_symbols = lambda pkg, **kw: [("test_mod", cls)]
        original_find = mod.find_module_for_symbol
        mod.find_module_for_symbol = lambda pkg, sym: _fake_pkg.modules[0]  # type: ignore[assignment]
        try:
            result = resolve_class_method(_fake_pkg, "MyClass.do_stuff", source=False)
            assert result is not None
            assert result.success is True
            assert result.data["symbol"]["name"] == "do_stuff"
        finally:
            mod.search_symbols = original_search
            mod.find_module_for_symbol = original_find

    def test_resolve_class_method_not_found(self, _fake_pkg: PackageInfo) -> None:
        """resolve_class_method returns error for missing method."""
        import axm_ast.tools.inspect_resolve as mod
        from axm_ast.tools.inspect_resolve import resolve_class_method

        cls = _fake_pkg.modules[0].classes[0]
        original = mod.search_symbols
        mod.search_symbols = lambda pkg, **kw: [("test_mod", cls)]
        try:
            result = resolve_class_method(
                _fake_pkg, "MyClass.nonexistent", source=False
            )
            assert result is not None
            assert result.success is False
            assert result.error is not None
            assert "nonexistent" in result.error
        finally:
            mod.search_symbols = original


class TestModuleFallback:
    """Verify fallback when symbol not found in any module."""

    def test_resolve_module_symbol_returns_none_no_match(
        self, _fake_pkg: PackageInfo
    ) -> None:
        """resolve_module_symbol returns None when no module prefix matches."""
        from axm_ast.tools.inspect_resolve import resolve_module_symbol

        result = resolve_module_symbol(_fake_pkg, "nonexistent.thing", source=False)
        assert result is None

    def test_resolve_module_symbol_finds_function(self, _fake_pkg: PackageInfo) -> None:
        """resolve_module_symbol finds core.helper."""
        from axm_ast.tools.inspect_resolve import resolve_module_symbol

        result = resolve_module_symbol(_fake_pkg, "core.helper", source=False)
        assert result is not None
        assert result.success is True
        assert result.data["symbol"]["name"] == "helper"
