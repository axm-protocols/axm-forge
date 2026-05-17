"""Split from ``test_inspect_resolve.py``."""

from axm_ast.models import PackageInfo


def test_find_symbol_file_returns_relative_path(_fake_pkg: PackageInfo) -> None:
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


def test_find_symbol_file_returns_empty_when_not_found(_fake_pkg: PackageInfo) -> None:
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
