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


def test_flows_hook_missing_path_fails(tmp_path: Path) -> None:
    """AC3 (failure mode): No valid path param causes failure."""
    hook = FlowsHook()
    ctx: dict[str, Any] = {"working_dir": str(tmp_path / "non_existent_dir")}

    result = hook.execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "not a directory" in result.error
