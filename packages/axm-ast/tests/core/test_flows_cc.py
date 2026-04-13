from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from axm_ast.core.flows import trace_flow


def _make_pkg(name: str = "fakepkg") -> Any:
    return SimpleNamespace(name=name, modules={})


def _make_callee(symbol: str, module: str = "mod", line: int = 1) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, module=module, line=line)


# ---------- Unit tests ----------


def test_trace_flow_basic():
    """PackageInfo with simple call chain returns ordered FlowSteps."""
    pkg = _make_pkg()

    # main -> helper -> leaf
    def fake_find_callees(p, symbol, _parse_cache=None):
        callees_map = {
            "main": [_make_callee("helper", "mod", 20)],
            "helper": [_make_callee("leaf", "mod", 30)],
            "leaf": [],
        }
        return callees_map.get(symbol, [])

    with (
        patch(
            "axm_ast.core.flows._find_symbol_location",
            return_value=("mod", 10),
        ),
        patch(
            "axm_ast.core.flows._build_package_symbols",
            return_value=frozenset({"main", "helper", "leaf"}),
        ),
        patch("axm_ast.core.flows.find_callees", side_effect=fake_find_callees),
    ):
        steps, truncated = trace_flow(pkg, "main", max_depth=5)

    assert truncated is False
    assert len(steps) == 3
    assert steps[0].name == "main"
    assert steps[0].depth == 0
    assert steps[1].name == "helper"
    assert steps[1].depth == 1
    assert steps[2].name == "leaf"
    assert steps[2].depth == 2
    # Chain correctness
    assert steps[2].chain == ["main", "helper", "leaf"]


def test_trace_flow_truncated():
    """max_depth=1 with deeper callees sets truncated=True."""
    pkg = _make_pkg()

    # main -> child; child -> grandchild (but depth=1 blocks expansion)
    def fake_find_callees(p, symbol, _parse_cache=None):
        callees_map = {
            "main": [_make_callee("child", "mod", 20)],
            "child": [_make_callee("grandchild", "mod", 30)],
        }
        return callees_map.get(symbol, [])

    with (
        patch(
            "axm_ast.core.flows._find_symbol_location",
            return_value=("mod", 10),
        ),
        patch(
            "axm_ast.core.flows._build_package_symbols",
            return_value=frozenset({"main", "child", "grandchild"}),
        ),
        patch("axm_ast.core.flows.find_callees", side_effect=fake_find_callees),
        patch(
            "axm_ast.core.flows._has_expandable_callees",
            return_value=True,
        ),
    ):
        steps, truncated = trace_flow(pkg, "main", max_depth=1)

    assert truncated is True
    # Only main (depth 0) and child (depth 1) — grandchild not expanded
    assert len(steps) == 2
    assert steps[0].name == "main"
    assert steps[1].name == "child"


# ---------- Edge cases ----------


def test_trace_flow_circular_calls():
    """A->B->A: visited set prevents infinite loop."""
    pkg = _make_pkg()

    def fake_find_callees(p, symbol, _parse_cache=None):
        callees_map = {
            "func_a": [_make_callee("func_b", "mod", 20)],
            "func_b": [_make_callee("func_a", "mod", 10)],
        }
        return callees_map.get(symbol, [])

    with (
        patch(
            "axm_ast.core.flows._find_symbol_location",
            return_value=("mod", 10),
        ),
        patch(
            "axm_ast.core.flows._build_package_symbols",
            return_value=frozenset({"func_a", "func_b"}),
        ),
        patch("axm_ast.core.flows.find_callees", side_effect=fake_find_callees),
    ):
        steps, truncated = trace_flow(pkg, "func_a", max_depth=10)

    assert truncated is False
    # Only 2 steps: func_a and func_b — no infinite loop
    assert len(steps) == 2
    names = [s.name for s in steps]
    assert "func_a" in names
    assert "func_b" in names
