"""Tests for TraceSourceHook — enriched BFS trace with function source code."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.hooks.trace_source import TraceSourceHook, _parse_entry, _resolve_scope

# ─── _parse_entry (unit) ────────────────────────────────────────────────────


class TestParseEntry:
    """Tests for _parse_entry helper."""

    def test_swe_bench_format(self) -> None:
        """SWE-bench: 'test_name (module.path.ClassName)'."""
        symbol, test_dir = _parse_entry("test_foo (httpwrappers.tests.HttpTests)")
        assert symbol == "test_foo"
        assert test_dir == "httpwrappers"

    def test_pytest_format(self) -> None:
        """Pytest: 'tests/path/file.py::Class::method'."""
        symbol, test_dir = _parse_entry("tests/unit/test_core.py::TestCore::test_run")
        assert symbol == "test_run"
        assert test_dir == "tests/unit"

    def test_simple_symbol(self) -> None:
        """Simple: 'HttpResponse'."""
        symbol, test_dir = _parse_entry("HttpResponse")
        assert symbol == "HttpResponse"
        assert test_dir is None

    def test_comma_separated_uses_first(self) -> None:
        """Multiple entries: use the first one."""
        symbol, test_dir = _parse_entry("test_alpha (mod.Tests), test_beta (mod.Tests)")
        assert symbol == "test_alpha"
        assert test_dir == "mod"

    def test_whitespace_stripped(self) -> None:
        symbol, test_dir = _parse_entry("  HttpResponse  ")
        assert symbol == "HttpResponse"
        assert test_dir is None

    def test_pytest_single_colon_colon(self) -> None:
        """Pytest: 'tests/file.py::test_function' (no class)."""
        symbol, test_dir = _parse_entry("tests/test_core.py::test_run")
        assert symbol == "test_run"
        assert test_dir == "tests"


# ─── _resolve_scope (unit) ──────────────────────────────────────────────────


class TestResolveScope:
    """Tests for _resolve_scope helper."""

    def test_none_test_dir_returns_base(self, tmp_path: Path) -> None:
        result = _resolve_scope(tmp_path, None)
        assert result == tmp_path

    def test_existing_test_dir(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests" / "myapp"
        test_dir.mkdir(parents=True)
        result = _resolve_scope(tmp_path, "myapp")
        assert result == test_dir

    def test_nonexistent_test_dir_falls_back(self, tmp_path: Path) -> None:
        result = _resolve_scope(tmp_path, "nonexistent")
        assert result == tmp_path

    def test_tests_prefix_preserved(self, tmp_path: Path) -> None:
        """test_dir starting with 'tests/' is used directly."""
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        result = _resolve_scope(tmp_path, "tests/unit")
        assert result == test_dir


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
        """Unknown entry symbol → empty trace, still success."""
        result = hook.execute(
            context={"working_dir": str(trace_pkg)},
            entry="nonexistent_xyz",
        )
        assert result.success
        trace = result.metadata.get("trace", [])
        assert trace == []
