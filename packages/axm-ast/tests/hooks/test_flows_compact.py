from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture()
def mini_package(tmp_path: Path) -> Path:
    """Create a minimal Python package for flow tracing."""
    src = tmp_path / "src" / "mini"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text(
        textwrap.dedent("""\
            def greet(name: str) -> str:
                return hello(name)

            def hello(name: str) -> str:
                return f"Hello, {name}"
        """)
    )
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "mini"
            version = "0.0.1"
            [tool.hatch.build.targets.wheel]
            packages = ["src/mini"]
        """)
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestBuildTraceOptsCompactPassthrough:
    """_build_trace_opts must pass 'compact' through to opts.detail."""

    def test_compact_passthrough(self) -> None:
        from axm_ast.hooks.flows import _build_trace_opts

        opts, is_compact = _build_trace_opts({"detail": "compact"})
        assert opts.detail == "compact"
        assert is_compact is True

    def test_trace_unchanged(self) -> None:
        from axm_ast.hooks.flows import _build_trace_opts

        opts, is_compact = _build_trace_opts({"detail": "trace"})
        assert opts.detail == "trace"
        assert is_compact is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBuildTraceOptsEdgeCases:
    """Non-compact details must pass through unchanged."""

    def test_source_detail(self) -> None:
        from axm_ast.hooks.flows import _build_trace_opts

        opts, is_compact = _build_trace_opts({"detail": "source"})
        assert opts.detail == "source"
        assert is_compact is False


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestHookToolCompactEquivalence:
    """Hook and tool must produce identical compact output."""

    def test_hook_tool_compact_equivalence(self, mini_package: Path) -> None:
        from axm_ast.hooks.flows import FlowsHook
        from axm_ast.tools.flows import FlowsTool

        hook = FlowsHook()
        tool = FlowsTool()

        hook_result = hook.execute(
            context={"working_dir": str(mini_package)},
            entry="greet",
            detail="compact",
        )
        tool_result = tool.execute(
            path=str(mini_package),
            entry="greet",
            detail="compact",
        )

        assert hook_result.success, hook_result.error
        assert tool_result.success, tool_result.error

        hook_traces = hook_result.metadata.get("traces", "")
        tool_data = (
            tool_result.data
            if isinstance(tool_result.data, str)
            else tool_result.data.get("traces", "")
        )

        assert hook_traces == tool_data
