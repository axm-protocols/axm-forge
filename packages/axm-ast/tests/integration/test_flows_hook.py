"""Unit tests for FlowsHook."""

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_ast.hooks.flows import FlowsHook
from tests.integration._helpers import _write_pkg


def test_flows_hook_returns_traces(tmp_path: Path) -> None:
    """AC3: ast:flows hook calls trace_flow and returns traces."""
    # Setup a simple fixture package
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def entry_point():
    caller()

def caller():
    pass
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    # Execute without entry filter (discovers entries automatically)
    result = hook.execute(ctx)

    assert result.success is True
    assert "traces" in result.metadata

    traces = result.metadata["traces"]
    # Dictionary of traces returned for multiple entry points
    assert isinstance(traces, dict)


def test_flows_hook_with_entry_filter(tmp_path: Path) -> None:
    """AC4: ast:flows supports entry param and detail parameter."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def target_func():
    other_func()

def other_func():
    pass
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="target_func", detail="compact")

    assert result.success is True
    assert "traces" in result.metadata

    # Compact mode returns a formatted string (AXM-939)
    traces = result.metadata["traces"]
    assert isinstance(traces, str)

    # Ensure trace includes target_func and other_func
    assert "target_func" in traces
    assert "other_func" in traces


def test_trace_entries_dedup_class_when_methods_listed(tmp_path: Path) -> None:
    """AC1: When symbols contain both Foo and Foo.bar, only Foo.bar is traced."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

class Foo:
    def bar(self):
        helper()

    def baz(self):
        helper()

    def other(self):
        pass
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Foo\nFoo.bar\nFoo.baz")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)
    assert "Foo.bar" in traces
    assert "Foo.baz" in traces
    assert "Foo" not in traces


def test_trace_entries_keeps_class_without_methods(tmp_path: Path) -> None:
    """AC2: When symbols contain only Foo (no qualified methods), Foo is traced."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
class Foo:
    def bar(self):
        pass
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Foo")

    assert result.success is True
    traces = result.metadata["traces"]
    # Single entry → returned as list
    assert isinstance(traces, list)


def test_trace_entries_only_qualified(tmp_path: Path) -> None:
    """AC3: When symbols contain only qualified methods, they are all traced."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

class Foo:
    def bar(self):
        helper()

    def baz(self):
        helper()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Foo.bar\nFoo.baz")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)
    assert "Foo.bar" in traces
    assert "Foo.baz" in traces


def test_trace_entries_mixed_classes(tmp_path: Path) -> None:
    """Foo skipped (has qualified child), Bar kept (no qualified child)."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

class Foo:
    def bar(self):
        helper()

class Bar:
    def qux(self):
        helper()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Foo\nFoo.bar\nBar")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)
    assert "Foo.bar" in traces
    assert "Bar" in traces
    assert "Foo" not in traces


def test_trace_entries_nested_class_dedup(tmp_path: Path) -> None:
    """Edge case: Outer.Inner is deduped when Outer.Inner.method is listed.

    The rsplit dedup correctly identifies Outer.Inner as a parent of
    Outer.Inner.method, so the parent is removed from the symbol list.
    """
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

class Outer:
    class Inner:
        def method(self):
            helper()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Outer.Inner\nOuter.Inner.method")

    # After dedup only Outer.Inner.method remains; _find_symbol_location
    # cannot resolve nested-class qualified names → ValueError → fail
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error


def test_trace_entries_duplicate_symbols(tmp_path: Path) -> None:
    """Edge case: duplicate symbols are traced once without error."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

class Foo:
    def bar(self):
        helper()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="Foo.bar\nFoo.bar")

    assert result.success is True
    traces = result.metadata["traces"]
    # Single unique symbol after dedup → returned as list
    assert isinstance(traces, list)


# ---------------------------------------------------------------------------
# AXM-941: Multi-symbol trace deduplication
# ---------------------------------------------------------------------------


def test_trace_entries_dedup_shared_callees(tmp_path: Path) -> None:
    """Two symbols sharing callees → total steps < sum of individual traces."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def shared_a():
    pass

def shared_b():
    pass

def shared_c():
    pass

def alpha():
    shared_a()
    shared_b()
    shared_c()

def beta():
    shared_a()
    shared_b()
    shared_c()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="alpha\nbeta")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)
    assert "alpha" in traces
    assert "beta" in traces

    # Alpha should have all 3 shared callees; beta should have none (deduped)
    alpha_steps = traces["alpha"]
    beta_steps = traces["beta"]

    # Count total unique step names across both traces
    def _step_names(steps: Any) -> set[str]:
        if isinstance(steps, str):
            # Compact mode: parse names from tree lines
            return {
                line.split("(")[0].strip().lstrip("├─└│ ")
                for line in steps.splitlines()
                if line.strip()
            }
        return {s["name"] for s in steps}

    alpha_names = _step_names(alpha_steps)
    beta_names = _step_names(beta_steps)
    # Shared callees should NOT appear in beta (already seen in alpha)
    shared = {"shared_a", "shared_b", "shared_c"}
    assert shared <= alpha_names, (
        f"Alpha should contain shared callees, got {alpha_names}"
    )
    assert not (shared & beta_names), (
        f"Beta should not duplicate shared callees, got {beta_names}"
    )


def test_trace_entries_no_dedup_single(tmp_path: Path) -> None:
    """Single symbol → output identical to current behavior (no dedup needed)."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def helper():
    pass

def solo():
    helper()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="solo")

    assert result.success is True
    traces = result.metadata["traces"]
    # Single symbol returns list, not dict
    assert isinstance(traces, list)
    names = {s["name"] for s in traces}
    assert "solo" in names
    assert "helper" in names


def test_trace_entries_first_wins(tmp_path: Path) -> None:
    """A→C and B→C: C appears only in A's trace (first traced symbol wins)."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def common():
    pass

def func_a():
    common()

def func_b():
    common()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="func_a\nfunc_b")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)

    def _step_names(steps: Any) -> set[str]:
        if isinstance(steps, str):
            return {
                line.split("(")[0].strip().lstrip("├─└│ ")
                for line in steps.splitlines()
                if line.strip()
            }
        return {s["name"] for s in steps}

    a_names = _step_names(traces["func_a"])
    b_names = _step_names(traces["func_b"])

    assert "common" in a_names, "common should be in func_a's trace (first wins)"
    assert "common" not in b_names, "common should be deduped from func_b's trace"


def test_multi_symbol_trace_unique_count(tmp_path: Path) -> None:
    """FlowsHook with 4 symbols from same module → all steps globally unique."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def shared():
    pass

def w():
    shared()

def x():
    shared()

def y():
    shared()

def z():
    shared()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="w\nx\ny\nz")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)

    # Collect all step names across all traces
    all_names: list[str] = []
    for sym_traces in traces.values():
        if isinstance(sym_traces, str):
            for line in sym_traces.splitlines():
                stripped = line.split("(")[0].strip().lstrip("├─└│ ")
                if stripped:
                    all_names.append(stripped)
        else:
            all_names.extend(s["name"] for s in sym_traces)

    # Every name should appear exactly once (no duplicates across traces)
    assert len(all_names) == len(set(all_names)), (
        f"Duplicate steps found: {[n for n in all_names if all_names.count(n) > 1]}"
    )


def test_single_symbol_regression(tmp_path: Path) -> None:
    """Single-symbol path unchanged by dedup refactor."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def leaf():
    pass

def root():
    leaf()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="root")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, list)
    names = [s["name"] for s in traces]
    assert "root" in names
    assert "leaf" in names


def test_trace_entries_disjoint_traces(tmp_path: Path) -> None:
    """Edge: 2 symbols with zero overlap → both full traces preserved."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def leaf_x():
    pass

def leaf_y():
    pass

def branch_a():
    leaf_x()

def branch_b():
    leaf_y()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="branch_a\nbranch_b")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)

    def _step_names(steps: Any) -> set[str]:
        if isinstance(steps, str):
            return {
                line.split("(")[0].strip().lstrip("├─└│ ")
                for line in steps.splitlines()
                if line.strip()
            }
        return {s["name"] for s in steps}

    a_names = _step_names(traces["branch_a"])
    b_names = _step_names(traces["branch_b"])

    # No overlap → both traces should be fully preserved
    assert "branch_a" in a_names
    assert "leaf_x" in a_names
    assert "branch_b" in b_names
    assert "leaf_y" in b_names


def test_trace_entries_all_shared(tmp_path: Path) -> None:
    """Edge: 2 symbols with identical callees → second trace is minimal."""
    pkg_dir = tmp_path / "dummy_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("""
def shared():
    pass

def first():
    shared()

def second():
    shared()
""")

    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(pkg_dir)}

    result = hook.execute(ctx, entry="first\nsecond")

    assert result.success is True
    traces = result.metadata["traces"]
    assert isinstance(traces, dict)

    def _step_names(steps: Any) -> set[str]:
        if isinstance(steps, str):
            return {
                line.split("(")[0].strip().lstrip("├─└│ ")
                for line in steps.splitlines()
                if line.strip()
            }
        return {s["name"] for s in steps}

    first_names = _step_names(traces["first"])
    second_names = _step_names(traces["second"])

    # First gets shared, second only has itself (shared already seen)
    assert "shared" in first_names
    assert "first" in first_names
    assert "second" in second_names
    assert "shared" not in second_names


def test_flows_hook_missing_path_fails(tmp_path: Path) -> None:
    """AC3 (failure mode): No valid path param causes failure."""
    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(tmp_path / "non_existent_dir")}

    result = hook.execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "not a directory" in result.error


# ─── Functional: FlowsTool + FlowsHook with compact ─────────────────────────

SAMPLE_PKG_FILES: dict[str, str] = {
    "__init__.py": "",
    "main.py": (
        "def main():\n"
        "    caller()\n\n"
        "def caller():\n"
        "    helper()\n\n"
        "def helper():\n"
        "    pass\n"
    ),
}


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


class TestFlowsHookCompactSingle:
    """FlowsHook with 1 entry, detail=compact returns compact markdown."""

    def test_flows_hook_compact_single(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SAMPLE_PKG_FILES)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(ctx, entry="main", detail="compact")
        assert result.success is True
        assert "traces" in result.metadata
        traces = result.metadata["traces"]
        # Compact mode returns a string (AXM-1009)
        assert isinstance(traces, str)


class TestFlowsHookCompactMulti:
    """FlowsHook with 3 entries, detail=compact → concatenated sections with headers."""

    def test_flows_hook_compact_multi(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": (
                    "def alpha():\n"
                    "    pass\n\n"
                    "def beta():\n"
                    "    pass\n\n"
                    "def gamma():\n"
                    "    pass\n"
                ),
            },
        )
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(ctx, entry="alpha\nbeta\ngamma", detail="compact")
        assert result.success is True
        traces = result.metadata["traces"]
        # Multi-entry compact returns concatenated string (AXM-1009)
        assert isinstance(traces, str)
        assert "alpha" in traces
        assert "beta" in traces
        assert "gamma" in traces


class TestCompactSingleSymbol:
    """Only 1 entry in multi-symbol list → no header, just tree."""

    def test_single_symbol_no_header(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SAMPLE_PKG_FILES)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(ctx, entry="main", detail="compact")
        assert result.success is True
        traces = result.metadata["traces"]
        # Single entry should not have section header
        if isinstance(traces, str):
            # No markdown header like "## main"
            assert not traces.startswith("##")


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


class TestDetailEdgeCasesIntegration:
    """Boundary conditions for detail validation (integration)."""

    def test_flows_hook_invalid_detail(self, tmp_path: object) -> None:
        hook = FlowsHook()
        result = hook.execute(
            context={"working_dir": str(tmp_path)},
            entry="main",
            detail="full",
        )
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()


SIMPLE_PKG: dict[str, str] = {
    "__init__.py": "",
    "main.py": (
        "def main():\n"
        "    caller()\n\n"
        "def caller():\n"
        "    helper()\n\n"
        "def helper():\n"
        "    pass\n"
    ),
}

MULTI_ENTRY_PKG: dict[str, str] = {
    "__init__.py": "",
    "main.py": (
        "def alpha():\n"
        "    _shared()\n\n"
        "def beta():\n"
        "    _shared()\n\n"
        "def gamma():\n"
        "    pass\n\n"
        "def _shared():\n"
        "    pass\n"
    ),
}


class TestHookReturnsStringCompact:
    """AC1+AC2: FlowsHook.execute with detail=compact returns traces as str."""

    def test_hook_returns_string_compact(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SIMPLE_PKG)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(ctx, entry="main", detail="compact")

        assert result.success is True
        assert "traces" in result.metadata
        traces = result.metadata["traces"]
        # MUST be a string, not a dict or list
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Content should come from format_flow_compact
        assert "main" in traces


class TestHookMultiEntryConcatenated:
    """AC1: Multi-entry compact returns single string with headers per entry."""

    def test_hook_multi_entry_concatenated(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, MULTI_ENTRY_PKG)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(
            ctx,
            entry="alpha\nbeta\ngamma",
            detail="compact",
        )

        assert result.success is True
        traces = result.metadata["traces"]
        # MUST be a single concatenated string
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Must contain header for each entry point
        assert "alpha" in traces
        assert "beta" in traces
        assert "gamma" in traces


class TestHookCompactEmptyFlow:
    """Edge: no entry points found → empty string or skip message."""

    def test_empty_flow_returns_empty_string(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": "x = 1\n",
            },
        )
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        # No entry points in this package
        result = hook.execute(ctx, detail="compact")

        assert result.success is True
        traces = result.metadata["traces"]
        # Should be a string (empty or skip message), not a dict
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )


class TestHookCompactCircularCalls:
    """Edge: recursive function → truncated at max_depth, still returns string."""

    def test_circular_calls_returns_string(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(
            ctx,
            entry="func_a",
            detail="compact",
            max_depth=5,
        )

        assert result.success is True
        traces = result.metadata["traces"]
        # Must be string, not dict
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Should contain the entry point
        assert "func_a" in traces


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


class TestFlowsHookReturnsTracesFromFlowsRefactor:
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


class TestFlowsHookWithEntryFilterFromFlowsRefactor:
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


class TestMultiSymbolDedupFromFlowsRefactor:
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


class TestReexportChainFromFlowsRefactor:
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


class TestSingleEntryNotFoundFails:
    """FlowsHook.execute with an unknown single entry returns HookResult.fail."""

    def test_unknown_entry_returns_failure(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "main.py").write_text("def existing():\n    pass\n")

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="nonexistent",
        )

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


class TestMultiEntryOneMissingPartialSuccess:
    """FlowsHook.execute with a mix of valid and missing entries.

    Traces only the valid ones.
    """

    def test_missing_entry_skipped_valid_traced(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "main.py").write_text("def valid_func():\n    pass\n")

        hook = FlowsHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir)},
            entry="valid_func\nnonexistent",
        )

        assert result.success is True
        traces = result.metadata["traces"]
        assert isinstance(traces, dict)
        assert "valid_func" in traces
        assert "nonexistent" not in traces
