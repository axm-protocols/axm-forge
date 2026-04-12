from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm_ast.core.flows import FlowStep, trace_flow

# ── Helpers ───────────────────────────────────────────────────────────


def _make_callee(symbol: str, module: str = "mod", line: int = 1) -> MagicMock:
    """Create a mock CallSite."""
    cs = MagicMock()
    cs.symbol = symbol
    cs.module = module
    cs.line = line
    return cs


@pytest.fixture
def mock_pkg() -> MagicMock:
    """Minimal mock PackageInfo."""
    return MagicMock()


# ── Unit tests ────────────────────────────────────────────────────────


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_trace_flow_truncated_true(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """deep_fn with 3+ depth chain, max_depth=1 -> truncated is True."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"deep_fn", "mid_fn", "leaf_fn"})

    def _callees(
        pkg: object, symbol: str, _parse_cache: object = None
    ) -> list[MagicMock]:
        if symbol == "deep_fn":
            return [_make_callee("mid_fn")]
        if symbol == "mid_fn":
            return [_make_callee("leaf_fn")]
        return []

    mock_find_callees.side_effect = _callees

    _steps, truncated = trace_flow(mock_pkg, "deep_fn", max_depth=1)

    assert truncated is True


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_trace_flow_truncated_false(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """leaf_fn has no callees, max_depth=10 -> truncated is False."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"leaf_fn"})
    mock_find_callees.return_value = []

    _steps, truncated = trace_flow(mock_pkg, "leaf_fn", max_depth=10)

    assert truncated is False


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_trace_flow_actual_depth(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """main->a->b (depth 2), max_depth=3 -> actual depth <= 3."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"main", "a", "b"})

    def _callees(
        pkg: object, symbol: str, _parse_cache: object = None
    ) -> list[MagicMock]:
        if symbol == "main":
            return [_make_callee("a")]
        if symbol == "a":
            return [_make_callee("b")]
        return []

    mock_find_callees.side_effect = _callees

    steps, _truncated = trace_flow(mock_pkg, "main", max_depth=3)

    actual_depth = max(s.depth for s in steps)
    assert actual_depth <= 3
    assert actual_depth == 2


# ── Functional tests ──────────────────────────────────────────────────


@patch("axm_ast.core.cache.get_package")
@patch("axm_ast.core.flows.trace_flow")
def test_flows_tool_truncated_in_data(
    mock_trace: MagicMock,
    mock_get_pkg: MagicMock,
    tmp_path: object,
) -> None:
    """FlowsTool.execute with entry -> data['truncated'] is bool."""
    from axm_ast.tools.flows import FlowsTool

    mock_get_pkg.return_value = MagicMock()
    mock_trace.return_value = (
        [FlowStep(name="main", module="mod", line=1, depth=0, chain=["main"])],
        True,
    )

    tool = FlowsTool()
    result = tool.execute(path=str(tmp_path), entry="main", max_depth=1)

    assert result.success
    assert isinstance(result.data["truncated"], bool)


@patch("axm_ast.core.cache.get_package")
@patch("axm_ast.core.flows.trace_flow")
def test_flows_tool_depth_is_actual(
    mock_trace: MagicMock,
    mock_get_pkg: MagicMock,
    tmp_path: object,
) -> None:
    """Shallow graph with max_depth=10 -> data['depth'] < 10."""
    from axm_ast.tools.flows import FlowsTool

    mock_get_pkg.return_value = MagicMock()
    mock_trace.return_value = (
        [
            FlowStep(name="main", module="mod", line=1, depth=0, chain=["main"]),
            FlowStep(name="a", module="mod", line=5, depth=1, chain=["main", "a"]),
        ],
        False,
    )

    tool = FlowsTool()
    result = tool.execute(path=str(tmp_path), entry="main", max_depth=10)

    assert result.success
    assert result.data["depth"] < 10
    assert result.data["depth"] == 1


@patch("axm_ast.core.flows.format_flow_compact", return_value="main\n  └─ a")
@patch("axm_ast.core.cache.get_package")
@patch("axm_ast.core.flows.trace_flow")
def test_flows_tool_compact_has_truncated(
    mock_trace: MagicMock,
    mock_get_pkg: MagicMock,
    mock_compact: MagicMock,
    tmp_path: object,
) -> None:
    """Compact mode -> data['truncated'] present."""
    from axm_ast.tools.flows import FlowsTool

    mock_get_pkg.return_value = MagicMock()
    mock_trace.return_value = (
        [FlowStep(name="main", module="mod", line=1, depth=0, chain=["main"])],
        False,
    )

    tool = FlowsTool()
    result = tool.execute(
        path=str(tmp_path),
        entry="main",
        max_depth=5,
        detail="compact",
    )

    assert result.success
    assert "truncated" in result.data
    assert isinstance(result.data["truncated"], bool)


# ── Edge cases ────────────────────────────────────────────────────────


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_max_depth_zero_with_callees(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """max_depth=0, entry has callees -> truncated=True."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"entry_fn", "child_fn"})
    mock_find_callees.return_value = [_make_callee("child_fn")]

    steps, truncated = trace_flow(mock_pkg, "entry_fn", max_depth=0)

    assert truncated is True
    assert len(steps) == 1  # only entry node


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_max_depth_zero_no_callees(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """max_depth=0, entry has no callees -> truncated=False."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"entry_fn"})
    mock_find_callees.return_value = []

    steps, truncated = trace_flow(mock_pkg, "entry_fn", max_depth=0)

    assert truncated is False
    assert len(steps) == 1


@patch("axm_ast.core.flows._build_package_symbols")
@patch("axm_ast.core.flows.find_callees")
@patch("axm_ast.core.flows._find_symbol_location")
def test_exact_fit_not_truncated(
    mock_find_sym: MagicMock,
    mock_find_callees: MagicMock,
    mock_pkg_symbols: MagicMock,
    mock_pkg: MagicMock,
) -> None:
    """Graph depth exactly equals max_depth -> truncated=False."""
    mock_find_sym.return_value = ("mod", 1)
    mock_pkg_symbols.return_value = frozenset({"root", "a", "b"})

    def _callees(
        pkg: object, symbol: str, _parse_cache: object = None
    ) -> list[MagicMock]:
        if symbol == "root":
            return [_make_callee("a")]
        if symbol == "a":
            return [_make_callee("b")]
        return []  # b is a leaf

    mock_find_callees.side_effect = _callees

    steps, truncated = trace_flow(mock_pkg, "root", max_depth=2)

    assert truncated is False
    actual_depth = max(s.depth for s in steps)
    assert actual_depth == 2
