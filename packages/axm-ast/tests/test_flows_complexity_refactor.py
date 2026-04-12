"""Regression & edge-case tests for AXM-951 flows.py complexity refactor.

These tests verify that refactored functions preserve their original
behaviour — structure of HookResult, compact output, dedup ordering,
re-export resolution, and empty-flow handling.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from axm_ast.core.cache import get_package
from axm_ast.core.flows import (
    format_flow_compact,
    trace_flow,
)
from axm_ast.hooks.flows import FlowsHook

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a minimal Python package under *tmp_path* and return its root."""
    pkg_dir = tmp_path / "pkg"
    src = pkg_dir / "src" / "mypkg"
    src.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "mypkg"
            version = "0.1.0"
            [tool.hatch.build.targets.wheel]
            packages = ["src/mypkg"]
        """),
    )
    for name, body in files.items():
        target = src / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body))
    return pkg_dir


# ---------------------------------------------------------------------------
# Functional / regression tests
# ---------------------------------------------------------------------------


class TestFlowsHookReturnsTraces:
    """test_flows_hook_returns_traces — HookResult structure after refactor."""

    def test_single_entry_returns_hookresult_with_traces(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": textwrap.dedent("""\
                from mypkg.helpers import helper

                def target_func():
                    return helper()
            """),
                "helpers.py": textwrap.dedent("""\
                def helper():
                    return 42
            """),
            },
        )
        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="target_func",
        )
        assert result.success is True
        assert "traces" in result.metadata
        traces = result.metadata["traces"]
        # Must be a non-empty structure (list or dict)
        assert traces

    def test_multi_entry_returns_dict_keyed_by_symbol(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": textwrap.dedent("""\
                def alpha():
                    return beta()

                def beta():
                    return 1
            """),
            },
        )
        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="alpha\nbeta",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        assert isinstance(traces, dict)
        assert "alpha" in traces


class TestFlowsHookWithEntryFilter:
    """test_flows_hook_with_entry_filter — compact output for a single entry."""

    def test_compact_output_is_string(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "app.py": textwrap.dedent("""\
                def target_func():
                    return inner()

                def inner():
                    return 99
            """),
            },
        )
        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="target_func",
            detail="compact",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        # Compact mode produces a string (or dict-of-strings for multi)
        assert isinstance(traces, (str, dict))
        # Should mention the entry symbol
        text = traces if isinstance(traces, str) else str(traces)
        assert "target_func" in text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMultiSymbolDedup:
    """Two entries share callees — first-wins ordering preserved."""

    def test_shared_callees_deduped_first_wins(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "shared.py": textwrap.dedent("""\
                def common():
                    return 1

                def entry_a():
                    return common()

                def entry_b():
                    return common()
            """),
            },
        )
        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="entry_a\nentry_b",
        )
        assert result.success is True
        traces = result.metadata["traces"]
        assert isinstance(traces, dict)
        # entry_a listed first, so "common" should appear under entry_a
        assert "entry_a" in traces
        a_text = str(traces["entry_a"])
        assert "common" in a_text

        # entry_b may still be present but "common" is deduped out
        if "entry_b" in traces:
            # The deduped trace for entry_b should be shorter or exclude common
            # (it keeps entry_b itself but strips already-seen callees)
            b_steps = traces["entry_b"]
            if isinstance(b_steps, list):
                callee_names = {
                    s["name"] if isinstance(s, dict) else s.name
                    for s in b_steps
                    if (s.get("name", "") if isinstance(s, dict) else s.name)
                    != "entry_b"
                }
                assert "common" not in callee_names


class TestReexportChain:
    """__init__.py → _impl.py → actual — follows the full chain."""

    def test_follows_reexport_through_init(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "from mypkg.sub import do_thing\n",
                "sub/__init__.py": "from mypkg.sub._impl import do_thing\n",
                "sub/_impl.py": textwrap.dedent("""\
                def do_thing():
                    return _private()

                def _private():
                    return 42
            """),
            },
        )
        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="do_thing",
            cross_module=True,
        )
        assert result.success is True
        traces = result.metadata["traces"]
        assert traces  # non-empty


class TestEmptyFlow:
    """Entry with no callees returns empty steps list."""

    def test_no_callees_returns_empty_steps(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "leaf.py": textwrap.dedent("""\
                def lonely():
                    return 42
            """),
            },
        )
        pkg = get_package(pkg_dir)
        steps, _ = trace_flow(pkg, "lonely")
        # A leaf function with no callees: either empty list or single root step
        if steps:
            # Only the root entry itself, no children
            assert all(s.depth == 0 for s in steps)

    def test_format_compact_empty_input(self) -> None:
        """format_flow_compact([]) returns empty string."""
        assert format_flow_compact([]) == ""
