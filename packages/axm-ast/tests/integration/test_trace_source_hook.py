"""Tests for TraceSourceHook — enriched BFS trace with function source code."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestTraceSourceHookExecuteIntegration:
    """Integration tests for the full execute flow."""

    @patch("axm_ast.hooks.trace_source.trace_flow")
    @patch("axm_ast.hooks.trace_source.analyze_package")
    def test_swe_bench_entry_scopes_path(
        self,
        mock_analyze: MagicMock,
        mock_trace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """SWE-bench format entry scopes analyze_package to test dir."""
        # Setup: create tests/httpwrappers dir
        test_dir = tmp_path / "tests" / "httpwrappers"
        test_dir.mkdir(parents=True)

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_step = MagicMock()
        mock_step.model_dump.return_value = {"name": "test_foo", "depth": 0}
        mock_trace.return_value = ([mock_step], False)

        hook = TraceSourceHook()
        result = hook.execute(
            {},
            entry="test_memoryview_content (httpwrappers.tests.HttpResponseTests)",
            path=str(tmp_path),
        )

        assert result.success
        # Verify analyze_package was called with the scoped path
        mock_analyze.assert_called_once_with(test_dir)
        # Verify trace_flow got the parsed entry name
        mock_trace.assert_called_once()
        call_args = mock_trace.call_args
        assert call_args[0][1] == "test_memoryview_content"


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


class TestTraceSourceHook:
    """TraceSourceHook execution tests."""

    def test_trace_source_hook_execute(self, tmp_path: Path) -> None:
        """Valid context with working_dir → HookResult.ok with trace."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = TraceSourceHook()
        result = hook.execute({"working_dir": str(pkg_path)}, entry="main")
        assert result.success
        assert "trace" in result.metadata
        trace = result.metadata["trace"]
        assert len(trace) >= 1
        assert trace[0]["name"] == "main"
        assert "source" in trace[0]
        assert "def main" in trace[0]["source"]

    def test_trace_source_hook_no_entry(self, tmp_path: Path) -> None:
        """Missing entry param → HookResult.fail."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        hook = TraceSourceHook()
        result = hook.execute({"working_dir": str(tmp_path)})
        assert not result.success
        assert "entry" in (result.error or "").lower()

    def test_trace_source_hook_path_param(self, tmp_path: Path) -> None:
        """path param overrides working_dir from context."""
        from axm_ast.hooks.trace_source import TraceSourceHook

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def main():\n    pass\n",
            },
        )
        hook = TraceSourceHook()
        # working_dir points to tmp_path (no package), but path param is correct
        result = hook.execute(
            {"working_dir": str(tmp_path)},
            entry="main",
            path=str(pkg_path),
        )
        assert result.success
        assert "trace" in result.metadata
        assert result.metadata["trace"][0]["name"] == "main"
