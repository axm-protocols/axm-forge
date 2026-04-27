"""Integration tests for axm_ast.hooks.trace_source.TraceSourceHook."""

from __future__ import annotations

from pathlib import Path


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
