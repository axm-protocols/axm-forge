"""Split from ``test_inspect_resolve.py``."""

from axm_ast.models import PackageInfo


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
