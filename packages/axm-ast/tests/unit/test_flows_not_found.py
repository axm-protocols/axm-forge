from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.core.flows import FlowStep, trace_flow

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_trace_flow_symbol_not_found_raises(monkeypatch):
    """trace_flow raises ValueError when entry symbol is not found."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "nonexistent_symbol")


def test_trace_flow_found_no_callees(monkeypatch):
    """Found symbol with no callees returns [FlowStep] with count=1."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: ("some.module", 10),
    )
    monkeypatch.setattr(
        "axm_ast.core.flows._build_package_symbols",
        lambda _pkg: frozenset(),
    )
    monkeypatch.setattr(
        "axm_ast.core.flows.find_callees",
        lambda *a, **kw: [],
    )
    steps, _ = trace_flow(pkg, "leaf_function")
    assert len(steps) == 1
    assert steps[0].name == "leaf_function"
    assert steps[0].depth == 0


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_flows_tool_not_found_returns_error(monkeypatch, tmp_path):
    """FlowsTool.execute returns success=False when entry not found."""
    from axm_ast.tools.flows import FlowsTool

    monkeypatch.setattr(
        "axm_ast.core.flows.trace_flow",
        MagicMock(side_effect=ValueError("Symbol 'nonexistent' not found in package")),
    )
    monkeypatch.setattr(
        "axm_ast.core.cache.get_package",
        MagicMock(),
    )
    result = FlowsTool().execute(path=str(tmp_path), entry="nonexistent")
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error


def test_flows_hook_not_found_returns_fail(monkeypatch):
    """FlowsHook._trace_entries returns HookResult with success=False."""
    from axm_ast.hooks.flows import FlowsHook

    monkeypatch.setattr(
        "axm_ast.hooks.flows.trace_flow",
        MagicMock(side_effect=ValueError("Symbol 'nonexistent' not found")),
    )
    pkg = MagicMock()
    opts = MagicMock()
    result = FlowsHook._trace_entries(pkg, "nonexistent", opts)
    assert result.success is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_trace_flow_qualified_name_not_found_raises(monkeypatch):
    """Qualified name 'Foo.nonexistent' raises ValueError, not silent empty."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "Foo.nonexistent")


def test_trace_multi_entries_one_missing(monkeypatch):
    """Multi-symbol hook: valid symbol traced, missing one skipped gracefully."""
    from axm_ast.hooks.flows import FlowsHook

    def _mock_trace(pkg, sym, **kw):
        if sym == "nonexistent":
            msg = f"Symbol {sym!r} not found in package"
            raise ValueError(msg)
        return [FlowStep(name=sym, module="mod", line=1, depth=0, chain=[sym])]

    monkeypatch.setattr("axm_ast.hooks.flows.trace_flow", _mock_trace)
    monkeypatch.setattr("axm_ast.hooks.flows.build_callee_index", lambda _pkg: {})

    pkg = MagicMock()
    symbols = ["valid_func", "nonexistent"]
    kw = {
        "max_depth": 5,
        "cross_module": False,
        "detail": "trace",
        "exclude_stdlib": True,
    }
    format_fn = MagicMock(return_value="")
    result = FlowsHook._trace_multi_entries(pkg, symbols, kw, False, format_fn)
    assert result.success is True


def test_trace_flow_empty_package_raises(monkeypatch):
    """Package with no symbols raises ValueError for any entry."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "anything")
