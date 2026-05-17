"""Tests for axm_ast.core.flows.

Covers pydantic models (extra=forbid), trace_flow BFS, cross-module
resolution, workspace-level callees, compact formatting, truncation,
not-found handling, and detail validation.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from axm_ast.core.flows import (
    EntryPoint,
    FlowStep,
    find_callees_workspace,
    format_flow_compact,
    format_flows,
    trace_flow,
)
from axm_ast.hooks.flows import _build_trace_opts
from axm_ast.tools.flows import FlowsTool

# ── pydantic models (extra=forbid) ────────────────────────────────────


class TestEntryPointExtraForbid:
    """EntryPoint rejects unknown fields."""

    def test_entry_point_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            EntryPoint(
                name="x",
                module="m",
                kind="test",
                line=1,
                framework="pytest",
                extra_field="bad",  # type: ignore[call-arg]
            )


class TestFlowStepExtraForbid:
    """FlowStep rejects unknown fields."""

    def test_flow_step_rejects_extra(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            FlowStep(
                name="x",
                module="m",
                line=1,
                depth=0,
                chain=[],
                whoops=True,  # type: ignore[call-arg]
            )


class TestFormatFlows:
    """Test output formatting."""

    def test_format_empty(self) -> None:
        """Empty results → clean message."""
        assert format_flows([]) == "✅ No entry points detected."

    def test_format_results(self) -> None:
        """Results → grouped output."""
        entries = [
            EntryPoint(
                name="index",
                module="routes",
                kind="decorator",
                line=5,
                framework="flask",
            ),
            EntryPoint(
                name="test_foo",
                module="tests",
                kind="test",
                line=1,
                framework="pytest",
            ),
        ]
        output = format_flows(entries)
        assert "2 entry point(s)" in output
        assert "flask" in output
        assert "pytest" in output
        assert "index" in output
        assert "test_foo" in output


class TestFlowStepSourceField:
    """FlowStep model accepts optional source field."""

    def test_flowstep_source_default_none(self) -> None:
        """FlowStep without source → defaults to None."""
        step = FlowStep(name="f", module="m", line=1, depth=0, chain=["f"])
        assert step.source is None

    def test_flowstep_source_explicit(self) -> None:
        """FlowStep with explicit source → stored."""
        step = FlowStep(
            name="f", module="m", line=1, depth=0, chain=["f"], source="def f(): pass"
        )
        assert step.source == "def f(): pass"


class TestParseImportFromNodeBasic:
    """_parse_import_from_node extracts module and imported names."""

    def test_basic_import(self) -> None:
        """``from .response import HttpResponse`` → ('.response', ['HttpResponse'])."""
        from axm_ast.core.flows import _parse_import_from_node
        from axm_ast.core.parser import parse_source

        code = "from .response import HttpResponse\n"
        tree = parse_source(code)
        nodes = [
            n
            for n in getattr(tree.root_node, "children", [])
            if getattr(n, "type", "") == "import_from_statement"
        ]
        assert len(nodes) == 1
        module, names = _parse_import_from_node(nodes[0])
        assert module == ".response"
        assert names == ["HttpResponse"]


class TestParseImportFromNodeMulti:
    """_parse_import_from_node handles multi-name imports."""

    def test_multi_import(self) -> None:
        """``from .models import A, B`` → ('.models', ['A', 'B'])."""
        from axm_ast.core.flows import _parse_import_from_node
        from axm_ast.core.parser import parse_source

        code = "from .models import A, B\n"
        tree = parse_source(code)
        nodes = [
            n
            for n in getattr(tree.root_node, "children", [])
            if getattr(n, "type", "") == "import_from_statement"
        ]
        assert len(nodes) == 1
        module, names = _parse_import_from_node(nodes[0])
        assert module == ".models"
        assert set(names) == {"A", "B"}


class TestResolveRelativeModule:
    """_resolve_relative_module resolves dotted paths."""

    def test_single_dot(self) -> None:
        """.response from django.http → django.http.response."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module(".response", "django.http")
        assert result == "django.http.response"

    def test_double_dot(self) -> None:
        """..utils from django.http.response → django.utils."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module("..utils", "django.http.response")
        assert result == "django.http.utils"

    def test_dot_only(self) -> None:
        """. from django.http → django.http (no rel_name)."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module(".", "django.http")
        assert result == "django.http"


class TestEmptyFlowFormat:
    """format_flow_compact pure-function behavior on empty input."""

    def test_format_compact_empty_input(self) -> None:
        """format_flow_compact([]) returns empty string."""
        assert format_flow_compact([]) == ""


# ── trace_flow basics ─────────────────────────────────────────────────


def _make_pkg_ns(name: str = "fakepkg") -> Any:
    """Lightweight SimpleNamespace stand-in for PackageInfo."""
    return SimpleNamespace(name=name, modules={})


def _make_callee_ns(symbol: str, module: str = "mod", line: int = 1) -> SimpleNamespace:
    """SimpleNamespace stand-in for a CallSite."""
    return SimpleNamespace(symbol=symbol, module=module, line=line)


def test_trace_flow_basic() -> None:
    """PackageInfo with simple call chain returns ordered FlowSteps."""
    pkg = _make_pkg_ns()

    # main -> helper -> leaf
    def fake_find_callees(p: Any, symbol: str, _parse_cache: Any = None) -> Any:
        callees_map = {
            "main": [_make_callee_ns("helper", "mod", 20)],
            "helper": [_make_callee_ns("leaf", "mod", 30)],
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
    assert steps[2].chain == ["main", "helper", "leaf"]


def test_trace_flow_truncated() -> None:
    """max_depth=1 with deeper callees sets truncated=True."""
    pkg = _make_pkg_ns()

    def fake_find_callees(p: Any, symbol: str, _parse_cache: Any = None) -> Any:
        callees_map = {
            "main": [_make_callee_ns("child", "mod", 20)],
            "child": [_make_callee_ns("grandchild", "mod", 30)],
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
    assert len(steps) == 2
    assert steps[0].name == "main"
    assert steps[1].name == "child"


def test_trace_flow_circular_calls() -> None:
    """A->B->A: visited set prevents infinite loop."""
    pkg = _make_pkg_ns()

    def fake_find_callees(p: Any, symbol: str, _parse_cache: Any = None) -> Any:
        callees_map = {
            "func_a": [_make_callee_ns("func_b", "mod", 20)],
            "func_b": [_make_callee_ns("func_a", "mod", 10)],
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
    assert len(steps) == 2
    names = [s.name for s in steps]
    assert "func_a" in names
    assert "func_b" in names


# ── cross-module resolution ───────────────────────────────────────────


class TestFindSourceModuleUnit:
    """Unit tests for _find_source_module (no real I/O)."""

    def test_find_source_module_missing(self, tmp_path: Path) -> None:
        """Unknown context → returns None."""
        from axm_ast.core.flows import _find_source_module
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])

        result = _find_source_module(pkg, "nonexistent", "no.such.module")
        assert result is None


class TestTryResolveCalleeUnit:
    """Unit tests for _try_resolve_callee (no real I/O)."""

    def test_try_resolve_callee_stdlib(self, tmp_path: Path) -> None:
        """CallSite with stdlib symbol → returns None."""
        from axm_ast.core.flows import _try_resolve_callee
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        callee = CallSite(
            symbol="len",
            module="builtins",
            line=1,
            column=0,
            context="",
            call_expression="len(x)",
        )
        pkg = PackageInfo(name="test", root=tmp_path, modules=[])

        result = _try_resolve_callee(callee, pkg)
        assert result is None


class TestCrossModuleEdgeCasesUnit:
    """Unit edge cases for _resolve_cross_module_callees (no real I/O)."""

    def test_missing_source_module_skipped(self, tmp_path: Path) -> None:
        """Both lookups fail → callee silently skipped."""
        from axm_ast.core.flows import (
            _CrossModuleContext,
            _ResolutionScope,
            _resolve_cross_module_callees,
        )
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])
        ctx = _CrossModuleContext(visited=set(), queue=deque(), steps=[])
        scope = _ResolutionScope(
            current_mod="nonexistent.mod",
            current_pkg=pkg,
            original_pkg=pkg,
            depth=0,
            current_chain=["entry"],
        )

        callee = CallSite(
            symbol="unknown_fn",
            module="no.module",
            line=1,
            column=0,
            context="missing",
            call_expression="unknown_fn()",
        )
        _resolve_cross_module_callees([callee], scope, ctx)
        assert ctx.steps == []

    def test_already_visited_skipped(self, tmp_path: Path) -> None:
        """Same (dotted, symbol) pair seen → skip without duplicate FlowStep."""
        from axm_ast.core.flows import (
            _CrossModuleContext,
            _ResolutionScope,
            _resolve_cross_module_callees,
        )
        from axm_ast.models.calls import CallSite
        from axm_ast.models.nodes import PackageInfo

        pkg = PackageInfo(name="test", root=tmp_path, modules=[])
        ctx = _CrossModuleContext(
            visited={("target.module", "some_func")},
            queue=deque(),
            steps=[],
        )
        scope = _ResolutionScope(
            current_mod="caller",
            current_pkg=pkg,
            original_pkg=pkg,
            depth=0,
            current_chain=["entry"],
        )

        callee = CallSite(
            symbol="some_func",
            module="caller",
            line=1,
            column=0,
            context="",
            call_expression="some_func()",
        )
        _resolve_cross_module_callees([callee], scope, ctx)
        assert len(ctx.steps) == 0


# ── workspace-level (find_callees_workspace) ──────────────────────────


def test_find_callees_workspace_iterates_all_packages() -> None:
    """Workspace-level callees returns results from all packages.

    Results include pkg_name:: prefix.
    """
    call_a = MagicMock(
        module="mod_a",
        symbol="func_x",
        line=10,
        context="x()",
        call_expression="func_x()",
    )
    call_b = MagicMock(
        module="mod_b",
        symbol="func_y",
        line=20,
        context="y()",
        call_expression="func_y()",
    )

    pkg1 = MagicMock()
    pkg1.name = "pkg_alpha"
    pkg2 = MagicMock()
    pkg2.name = "pkg_beta"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.side_effect = [
            [call_a],
            [call_b],
        ]

        result = find_callees_workspace(ws, "some_symbol")

    assert len(result) == 2
    assert result[0].module == "pkg_alpha::mod_a"
    assert result[1].module == "pkg_beta::mod_b"


def test_find_callees_workspace_shares_parse_cache() -> None:
    """A single cache dict is passed to all find_callees calls across packages."""
    pkg1 = MagicMock()
    pkg1.name = "pkg1"
    pkg2 = MagicMock()
    pkg2.name = "pkg2"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.return_value = []

        find_callees_workspace(ws, "sym")

        assert mock_find.call_count == 2
        cache1 = mock_find.call_args_list[0][1]["_parse_cache"]
        cache2 = mock_find.call_args_list[1][1]["_parse_cache"]
        assert cache1 is cache2
        assert isinstance(cache1, dict)


def test_find_callees_workspace_symbol_in_one_package() -> None:
    """Symbol found in only one of three packages.

    Returns prefixed callees from that one.
    """
    call_site = MagicMock(
        module="helpers",
        symbol="do_thing",
        line=5,
        context="..",
        call_expression="do_thing()",
    )

    pkg1 = MagicMock()
    pkg1.name = "alpha"
    pkg2 = MagicMock()
    pkg2.name = "beta"
    pkg3 = MagicMock()
    pkg3.name = "gamma"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2, pkg3]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.side_effect = [
            [],
            [call_site],
            [],
        ]

        result = find_callees_workspace(ws, "do_thing")

    assert len(result) == 1
    assert result[0].module == "beta::helpers"


def test_find_callees_workspace_symbol_not_found() -> None:
    """Non-existent symbol across workspace returns empty list."""
    pkg1 = MagicMock()
    pkg1.name = "a"
    pkg2 = MagicMock()
    pkg2.name = "b"

    ws = MagicMock()
    ws.packages = [pkg1, pkg2]

    with patch("axm_ast.core.flows.find_callees") as mock_find:
        mock_find.return_value = []

        result = find_callees_workspace(ws, "nonexistent")

    assert result == []


# ── compact mode ──────────────────────────────────────────────────────


def _step(
    name: str, module: str, line: int, depth: int, chain: list[str] | None = None
) -> FlowStep:
    """Create a FlowStep with defaults."""
    return FlowStep(
        name=name,
        module=module,
        line=line,
        depth=depth,
        chain=chain or [],
    )


class TestFormatFlowCompactSingleDepth:
    """3 FlowSteps at depth 0, 1, 1 → tree with root + 2 children."""

    def test_format_flow_compact_single_depth(self) -> None:
        steps = [
            _step("main", "mod", 1, 0),
            _step("caller", "mod", 5, 1),
            _step("helper", "mod", 10, 1),
        ]
        result = format_flow_compact(steps)
        assert "main" in result
        assert "caller" in result
        assert "helper" in result
        lines = result.strip().splitlines()
        assert lines[0].strip() == "main  (mod:1)"
        assert any("├" in line or "└" in line for line in lines[1:])


class TestFormatFlowCompactNested:
    """Steps at depth 0, 1, 2, 1 → proper indentation with box-drawing chars."""

    def test_format_flow_compact_nested(self) -> None:
        steps = [
            _step("main", "mod", 1, 0),
            _step("caller", "mod", 5, 1),
            _step("deep", "mod", 8, 2),
            _step("other", "mod", 12, 1),
        ]
        result = format_flow_compact(steps)
        lines = result.strip().splitlines()
        assert len(lines) == 4
        depth1_indent = len(lines[1]) - len(lines[1].lstrip())
        depth2_indent = len(lines[2]) - len(lines[2].lstrip())
        assert depth2_indent > depth1_indent


class TestFormatFlowCompactEmpty:
    """Empty step list → empty string or 'No flows traced'."""

    def test_format_flow_compact_empty(self) -> None:
        result = format_flow_compact([])
        assert result == "" or "No flows" in result


class TestCompactExcludesChain:
    """Steps with chain populated → output contains no chain data."""

    def test_compact_excludes_chain(self) -> None:
        steps = [
            _step("main", "mod", 1, 0, chain=["main"]),
            _step("caller", "mod", 5, 1, chain=["main", "caller"]),
            _step("helper", "mod", 10, 2, chain=["main", "caller", "helper"]),
        ]
        result = format_flow_compact(steps)
        assert "['main'" not in result
        assert "main, caller" not in result
        assert "main" in result
        assert "caller" in result


# ── format_flow_compact ───────────────────────────────────────────────


class TestFormatFlowCompact:
    """Unit tests for format_flow_compact."""

    def test_empty_steps_returns_empty_string(self) -> None:
        assert format_flow_compact([]) == ""

    def test_single_root_step(self) -> None:
        steps = [
            FlowStep(name="main", module="pkg.main", line=10, depth=0, chain=["main"]),
        ]
        result = format_flow_compact(steps)
        assert "main" in result
        assert "pkg.main:10" in result

    def test_nested_steps_use_connectors(self) -> None:
        steps = [
            FlowStep(name="root", module="m", line=1, depth=0, chain=["root"]),
            FlowStep(
                name="child",
                module="m",
                line=5,
                depth=1,
                chain=["root", "child"],
            ),
        ]
        result = format_flow_compact(steps)
        lines = result.splitlines()
        assert len(lines) == 2
        assert "└──" in lines[1] or "├──" in lines[1]

    def test_resolved_module_shown(self) -> None:
        steps = [
            FlowStep(
                name="func",
                module="a.b",
                line=1,
                depth=0,
                chain=["func"],
                resolved_module="x.y",
            ),
        ]
        result = format_flow_compact(steps)
        assert "→ x.y" in result


# ── truncation ────────────────────────────────────────────────────────


def _make_callee_mock(symbol: str, module: str = "mod", line: int = 1) -> MagicMock:
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
            return [_make_callee_mock("mid_fn")]
        if symbol == "mid_fn":
            return [_make_callee_mock("leaf_fn")]
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
            return [_make_callee_mock("a")]
        if symbol == "a":
            return [_make_callee_mock("b")]
        return []

    mock_find_callees.side_effect = _callees

    steps, _truncated = trace_flow(mock_pkg, "main", max_depth=3)

    actual_depth = max(s.depth for s in steps)
    assert actual_depth <= 3
    assert actual_depth == 2


@patch("axm_ast.core.cache.get_package")
@patch("axm_ast.core.flows.trace_flow")
def test_flows_tool_truncated_in_data(
    mock_trace: MagicMock,
    mock_get_pkg: MagicMock,
    tmp_path: object,
) -> None:
    """FlowsTool.execute with entry -> data['truncated'] is bool."""
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
    mock_find_callees.return_value = [_make_callee_mock("child_fn")]

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
            return [_make_callee_mock("a")]
        if symbol == "a":
            return [_make_callee_mock("b")]
        return []  # b is a leaf

    mock_find_callees.side_effect = _callees

    steps, truncated = trace_flow(mock_pkg, "root", max_depth=2)

    assert truncated is False
    actual_depth = max(s.depth for s in steps)
    assert actual_depth == 2


# ── not-found ─────────────────────────────────────────────────────────


def test_trace_flow_symbol_not_found_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """trace_flow raises ValueError when entry symbol is not found."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "nonexistent_symbol")


def test_trace_flow_found_no_callees(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_flows_tool_not_found_returns_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FlowsTool.execute returns success=False when entry not found."""
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


def test_flows_hook_not_found_returns_fail(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_trace_flow_qualified_name_not_found_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qualified name 'Foo.nonexistent' raises ValueError, not silent empty."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "Foo.nonexistent")


def test_trace_multi_entries_one_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-symbol hook: valid symbol traced, missing one skipped gracefully."""
    from axm_ast.hooks.flows import FlowsHook

    def _mock_trace(pkg: object, sym: str, **kw: object) -> list[FlowStep]:
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


def test_trace_flow_empty_package_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package with no symbols raises ValueError for any entry."""
    pkg = MagicMock()
    monkeypatch.setattr(
        "axm_ast.core.flows._find_symbol_location",
        lambda _pkg, _sym: (None, 0),
    )
    with pytest.raises(ValueError, match="not found"):
        trace_flow(pkg, "anything")


# ── detail validation ─────────────────────────────────────────────────


class TestTraceFlowInvalidDetailRaises:
    """trace_flow() must reject detail values outside the valid set."""

    def test_trace_flow_invalid_detail_raises(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="full")


class TestTraceFlowValidDetailsAccepted:
    """trace_flow() accepts each of the three valid detail values."""

    @pytest.mark.parametrize("detail", ["trace", "source", "compact"])
    def test_trace_flow_valid_details_accepted(
        self, detail: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = MagicMock()
        monkeypatch.setattr(
            "axm_ast.core.flows._find_symbol_location",
            lambda *a, **kw: ("some.module", 1),
        )
        monkeypatch.setattr(
            "axm_ast.core.flows._build_package_symbols",
            lambda _pkg: frozenset(),
        )
        monkeypatch.setattr(
            "axm_ast.core.flows.find_callees",
            lambda *a, **kw: [],
        )
        result, _ = trace_flow(pkg, "main", detail=detail)
        assert isinstance(result, list)
        assert len(result) >= 1


class TestFlowsToolValidDetails:
    """FlowsTool.execute() succeeds for each valid detail."""

    @pytest.mark.parametrize("detail", ["trace", "source", "compact"])
    def test_flows_tool_valid_details(
        self,
        detail: str,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_pkg = MagicMock()
        monkeypatch.setattr("axm_ast.core.cache.get_package", lambda *a, **kw: mock_pkg)
        monkeypatch.setattr(
            "axm_ast.core.flows.trace_flow", lambda *a, **kw: ([], False)
        )
        monkeypatch.setattr(
            "axm_ast.core.flows.format_flow_compact", lambda *a, **kw: ""
        )
        tool = FlowsTool()
        result = tool.execute(path=str(tmp_path), entry="main", detail=detail)
        assert result.success is True


class TestDetailEdgeCases:
    """Boundary conditions for detail validation."""

    def test_empty_string_detail_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="")

    def test_case_sensitivity_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="Trace")

    def test_none_detail_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail=None)

    def test_build_trace_opts_invalid_detail(self) -> None:
        with pytest.raises(ValueError, match="detail"):
            _build_trace_opts({"detail": "full"})
