"""TDD tests for compact output mode in ast_flows (AXM-939)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_ast.hooks.flows import FlowsHook
from axm_ast.tools.flows import FlowsTool


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


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


class TestFlowsToolCompactMode:
    """FlowsTool.execute(detail='compact') returns compact string, not JSON dicts."""

    def test_flows_tool_compact_mode(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SAMPLE_PKG_FILES)
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="compact")
        assert result.success is True
        # Compact mode should have a compact string representation
        assert "compact" in result.data
        compact_output = result.data["compact"]
        assert isinstance(compact_output, str)
        assert "main" in compact_output
        # Should NOT have step dicts in compact mode
        assert "steps" not in result.data


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


class TestFlowsToolTraceUnchanged:
    """FlowsTool.execute(detail='trace') → same output as before (regression)."""

    def test_flows_tool_trace_unchanged(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SAMPLE_PKG_FILES)
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="main", detail="trace")
        assert result.success is True
        # Trace mode should still return step dicts
        assert "steps" in result.data
        assert isinstance(result.data["steps"], list)
        for step in result.data["steps"]:
            assert "name" in step
            assert "depth" in step
            assert "chain" in step


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestCompactCircularCalls:
    """A→B→A at depth 2 → tree stops at visited node, no infinite loop."""

    def test_circular_calls(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        tool = FlowsTool()
        result = tool.execute(
            path=str(pkg_path), entry="func_a", detail="compact", max_depth=5
        )
        assert result.success is True
        # Should terminate without infinite loop
        compact = result.data.get("compact", "")
        assert isinstance(compact, str)


class TestCompactEmptyTrace:
    """Symbol not found → graceful empty output."""

    def test_empty_trace(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": "def foo():\n    pass\n",
            },
        )
        tool = FlowsTool()
        result = tool.execute(path=str(pkg_path), entry="nonexistent", detail="compact")
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


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
