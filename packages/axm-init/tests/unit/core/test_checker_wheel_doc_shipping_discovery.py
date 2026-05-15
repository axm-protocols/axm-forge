"""Unit test: auto-discovery of the new wheel-doc-shipping check (AXM-1715)."""

from __future__ import annotations

from axm_init.core.checker import _discover_checks


def test_discover_checks_includes_wheel_doc_shipping() -> None:
    registry = _discover_checks()
    pyproject_fns = registry.get("pyproject", [])
    names = {fn.__name__ for fn in pyproject_fns}
    assert "check_pyproject_wheel_doc_shipping" in names
