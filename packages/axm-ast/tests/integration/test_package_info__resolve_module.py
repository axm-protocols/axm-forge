from __future__ import annotations

from axm_ast.models import PackageInfo


def test_resolve_module_exact_match(_fake_pkg: PackageInfo) -> None:
    """resolve_module finds exact module name."""
    from axm_ast.tools.inspect_resolve import resolve_module

    result = resolve_module(_fake_pkg, "core")
    assert result is not None
    assert not hasattr(result, "success")  # Not a ToolResult
    assert result.name == "core"


def test_resolve_module_substring_match(_fake_pkg: PackageInfo) -> None:
    """resolve_module finds module by substring when unique."""
    from axm_ast.tools.inspect_resolve import resolve_module

    result = resolve_module(_fake_pkg, "sub.helpers")
    assert result is not None
    assert not hasattr(result, "success")
    assert result.name == "sub.helpers"


def test_resolve_module_returns_none_on_miss(_fake_pkg: PackageInfo) -> None:
    """resolve_module returns None when no match."""
    from axm_ast.tools.inspect_resolve import resolve_module

    result = resolve_module(_fake_pkg, "nonexistent")
    assert result is None
