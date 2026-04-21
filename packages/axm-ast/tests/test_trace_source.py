"""Tests for TraceSourceHook — enriched BFS trace with function source code."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.hooks.trace_source import TraceSourceHook

# ─── TraceSourceHook.execute ────────────────────────────────────────────────


class TestTraceSourceHookExecute:
    """Functional tests for TraceSourceHook.execute."""

    @pytest.fixture()
    def hook(self) -> TraceSourceHook:
        return TraceSourceHook()

    @pytest.fixture()
    def trace_pkg(self, tmp_path: Path) -> Path:
        """Create a small package for trace tests."""
        pkg = tmp_path / "tracedemo"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Trace demo."""\n')
        (pkg / "core.py").write_text(
            '"""Core module."""\n\n'
            "def greet(name: str) -> str:\n"
            '    """Say hello."""\n'
            '    return f"Hello {name}"\n\n\n'
            "def main() -> None:\n"
            '    """Entry point."""\n'
            '    greet("world")\n'
        )
        return pkg

    def test_missing_entry_param(self, hook: TraceSourceHook) -> None:
        result = hook.execute(context={"working_dir": "."})
        assert not result.success
        assert "entry" in (result.error or "")

    def test_bad_working_dir(self, hook: TraceSourceHook) -> None:
        result = hook.execute(
            context={"working_dir": "/nonexistent/path"},
            entry="foo",
        )
        assert not result.success

    def test_trace_returns_steps(self, hook: TraceSourceHook, trace_pkg: Path) -> None:
        result = hook.execute(
            context={"working_dir": str(trace_pkg)},
            entry="main",
        )
        assert result.success
        assert result.metadata is not None
        trace = result.metadata.get("trace", [])
        assert len(trace) >= 1
        names = [step["name"] for step in trace]
        assert "main" in names

    def test_trace_with_path_param(
        self, hook: TraceSourceHook, trace_pkg: Path
    ) -> None:
        """path param should override working_dir."""
        result = hook.execute(
            context={},
            entry="main",
            path=str(trace_pkg),
        )
        assert result.success

    def test_trace_unknown_symbol(self, hook: TraceSourceHook, trace_pkg: Path) -> None:
        """Unknown entry symbol → ValueError caught, fail result."""
        result = hook.execute(
            context={"working_dir": str(trace_pkg)},
            entry="nonexistent_xyz",
        )
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error
