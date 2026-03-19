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

    # When entry point is specific, traces are returned as a list
    traces = result.metadata["traces"]
    assert isinstance(traces, list)

    # Ensure trace includes target_func and other_func
    names = [s["name"] for s in traces]
    assert "target_func" in names
    assert "other_func" in names


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


def test_flows_hook_missing_path_fails(tmp_path: Path) -> None:
    """AC3 (failure mode): No valid path param causes failure."""
    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(tmp_path / "non_existent_dir")}

    result = hook.execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "not a directory" in result.error
