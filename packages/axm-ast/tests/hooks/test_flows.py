"""Unit tests for FlowsHook."""

from pathlib import Path
from typing import Any

from axm_ast.hooks.flows import FlowsHook


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

    assert result.success is True
    traces = result.metadata["traces"]
    # Outer.Inner should be deduped (its child Outer.Inner.method is listed)
    assert "Outer.Inner" not in traces


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
