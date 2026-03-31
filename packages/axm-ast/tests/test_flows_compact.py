"""TDD tests for compact output mode in ast_flows (AXM-939)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_ast.core.flows import FlowStep
from axm_ast.hooks.flows import FlowsHook
from axm_ast.tools.flows import FlowsTool

# format_flow_compact will be added by implementation; import lazily in tests
# so that pytest can collect the file even before the function exists.

# ─── Helpers ─────────────────────────────────────────────────────────────────


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


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


# ─── Unit: format_flow_compact ───────────────────────────────────────────────


def _format_compact(steps: list[FlowStep]) -> str:
    """Lazy import of format_flow_compact (not yet implemented)."""
    from axm_ast.core.flows import format_flow_compact

    return format_flow_compact(steps)


class TestFormatFlowCompactSingleDepth:
    """3 FlowSteps at depth 0, 1, 1 → tree with root + 2 children."""

    def test_format_flow_compact_single_depth(self) -> None:
        steps = [
            _step("main", "mod", 1, 0),
            _step("caller", "mod", 5, 1),
            _step("helper", "mod", 10, 1),
        ]
        result = _format_compact(steps)
        assert "main" in result
        assert "caller" in result
        assert "helper" in result
        # Root at depth 0 has no indent, children at depth 1 have tree chars
        lines = result.strip().splitlines()
        assert lines[0].strip() == "main"
        # Children should use box-drawing characters
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
        result = _format_compact(steps)
        lines = result.strip().splitlines()
        # Should have 4 lines (one per step)
        assert len(lines) == 4
        # Depth-2 node should be more indented than depth-1 nodes
        depth1_indent = len(lines[1]) - len(lines[1].lstrip())
        depth2_indent = len(lines[2]) - len(lines[2].lstrip())
        assert depth2_indent > depth1_indent


class TestFormatFlowCompactEmpty:
    """Empty step list → empty string or 'No flows traced'."""

    def test_format_flow_compact_empty(self) -> None:
        result = _format_compact([])
        assert result == "" or "No flows" in result


class TestCompactExcludesChain:
    """Steps with chain populated → output contains no chain data."""

    def test_compact_excludes_chain(self) -> None:
        steps = [
            _step("main", "mod", 1, 0, chain=["main"]),
            _step("caller", "mod", 5, 1, chain=["main", "caller"]),
            _step("helper", "mod", 10, 2, chain=["main", "caller", "helper"]),
        ]
        result = _format_compact(steps)
        # Chain paths should not appear in compact output
        assert "['main'" not in result
        assert "main, caller" not in result
        # But symbol names should still appear
        assert "main" in result
        assert "caller" in result


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
        # In compact mode, traces should be a compact string (not dicts)
        assert isinstance(traces, str) or (
            isinstance(traces, list) and all(isinstance(t, str) for t in traces)
        )


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
        # Multi-entry compact should have section headers
        if isinstance(traces, dict):
            assert len(traces) == 3
            for val in traces.values():
                assert isinstance(val, str)
        elif isinstance(traces, str):
            # Concatenated sections with headers
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
        assert result.success is True
        compact = result.data.get("compact", "")
        assert compact == "" or "No flows" in compact


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
