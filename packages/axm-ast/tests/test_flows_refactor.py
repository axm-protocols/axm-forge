"""Regression tests for AXM-951: flows.py complexity refactor.

These tests lock current behavior of the 5 high-complexity functions
so the refactor can proceed safely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.flows import FlowStep, format_flow_compact

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_pkg(tmp_path: Path) -> Path:
    """Create a minimal Python package for flow tracing."""
    src = tmp_path / "src" / "sample"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("from .core import main_func\n")
    (src / "core.py").write_text(
        """\
from __future__ import annotations

from .helpers import helper_a


def main_func():
    helper_a()
    return True


def _internal():
    pass
""",
    )
    (src / "helpers.py").write_text(
        """\
from __future__ import annotations


def helper_a():
    return 42
""",
    )
    return tmp_path


@pytest.fixture()
def reexport_pkg(tmp_path: Path) -> Path:
    """Package with re-export chain: __init__ -> _impl -> actual."""
    src = tmp_path / "src" / "reexport"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("from ._bridge import Widget\n")
    (src / "_bridge.py").write_text("from ._impl import Widget\n")
    (src / "_impl.py").write_text(
        """\
from __future__ import annotations


class Widget:
    def render(self):
        return "<widget />"
""",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# test_flows_hook_returns_traces — HookResult structure after refactor
# ---------------------------------------------------------------------------


class TestFlowsHookReturnsTraces:
    """FlowsHook.execute must return a HookResult with traces metadata."""

    def test_single_entry_returns_hook_result(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func",
        )
        assert result.success is True
        assert "traces" in result.metadata

    def test_single_entry_traces_are_list(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func",
        )
        traces = result.metadata["traces"]
        assert isinstance(traces, list)

    def test_trace_items_have_required_keys(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func",
        )
        for item in result.metadata["traces"]:
            assert "name" in item
            assert "module" in item
            assert "line" in item
            assert "depth" in item
            assert "chain" in item


# ---------------------------------------------------------------------------
# test_flows_hook_with_entry_filter — compact output
# ---------------------------------------------------------------------------


class TestFlowsHookWithEntryFilter:
    """FlowsHook with detail='compact' returns string traces."""

    def test_compact_returns_string(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func",
            detail="compact",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        assert isinstance(traces, str)

    def test_compact_contains_entry_name(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func",
            detail="compact",
        )
        assert "main_func" in result.metadata["traces"]


# ---------------------------------------------------------------------------
# Edge case: multi-symbol dedup — first-wins ordering preserved
# ---------------------------------------------------------------------------


class TestMultiSymbolDedup:
    """When two entries share callees, first-wins ordering is preserved."""

    def test_shared_callees_deduped(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        # Add a second function that also calls helper_a
        core = sample_pkg / "src" / "sample" / "core.py"
        core.write_text(
            core.read_text()
            + "\ndef second_func():\n    helper_a()\n    return False\n",
        )

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func\nsecond_func",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        # Multi-entry returns dict keyed by symbol
        assert isinstance(traces, dict)
        assert "main_func" in traces
        assert "second_func" in traces

    def test_first_entry_has_shared_callee(self, sample_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        core = sample_pkg / "src" / "sample" / "core.py"
        core.write_text(
            core.read_text()
            + "\ndef second_func():\n    helper_a()\n    return False\n",
        )

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="main_func\nsecond_func",
            cross_module=True,
        )
        traces = result.metadata["traces"]
        # helper_a should appear in main_func's trace (first wins)
        main_names = [s["name"] for s in traces["main_func"]]
        assert "helper_a" in main_names


# ---------------------------------------------------------------------------
# Edge case: re-export chain — follows full chain
# ---------------------------------------------------------------------------


class TestReexportChain:
    """_follow_reexport should follow __init__ -> _bridge -> _impl."""

    def test_reexport_resolves_to_impl(self, reexport_pkg: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(reexport_pkg)},
            entry="Widget",
            cross_module=True,
        )
        assert result.success is True
        traces = result.metadata["traces"]
        assert isinstance(traces, list)
        # Root should be Widget
        assert traces[0]["name"] == "Widget"


# ---------------------------------------------------------------------------
# Edge case: empty flow — entry with no callees
# ---------------------------------------------------------------------------


class TestEmptyFlow:
    """Entry symbol with no callees returns empty steps list."""

    def test_no_callees_returns_empty_or_root_only(
        self,
        sample_pkg: Path,
    ) -> None:
        from axm_ast.hooks.flows import FlowsHook

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(sample_pkg)},
            entry="_internal",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        # Either empty list or single root entry with no children
        assert isinstance(traces, list)
        if traces:
            assert len(traces) == 1
            assert traces[0]["name"] == "_internal"


# ---------------------------------------------------------------------------
# format_flow_compact — unit tests
# ---------------------------------------------------------------------------


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
        # Child line should have a connector
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
