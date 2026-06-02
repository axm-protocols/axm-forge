from __future__ import annotations

import pytest

from axm_ast.models import PackageInfo


@pytest.mark.parametrize(
    ("needle", "expected_name"),
    [
        pytest.param("core", "core", id="exact_match"),
        pytest.param("sub.helpers", "sub.helpers", id="substring_match"),
    ],
)
def test_resolve_module_match(
    _fake_pkg: PackageInfo, needle: str, expected_name: str
) -> None:
    """resolve_module finds a module by exact name or unique substring."""
    from axm_ast.tools.inspect_resolve import resolve_module

    result = resolve_module(_fake_pkg, needle)
    assert result is not None
    assert not hasattr(result, "success")  # Not a ToolResult
    assert result.name == expected_name


def test_resolve_module_returns_none_on_miss(_fake_pkg: PackageInfo) -> None:
    """resolve_module returns None when no match."""
    from axm_ast.tools.inspect_resolve import resolve_module

    result = resolve_module(_fake_pkg, "nonexistent")
    assert result is None
