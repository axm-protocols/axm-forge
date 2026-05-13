"""TDD tests for FlowsHook returning compact string instead of dict (AXM-1009)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm_ast.hooks.flows import FlowsHook

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a package from file dict and return path."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    for name, content in files.items():
        filepath = pkg / name
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return pkg


SIMPLE_PKG: dict[str, str] = {
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

MULTI_ENTRY_PKG: dict[str, str] = {
    "__init__.py": "",
    "main.py": (
        "def alpha():\n"
        "    _shared()\n\n"
        "def beta():\n"
        "    _shared()\n\n"
        "def gamma():\n"
        "    pass\n\n"
        "def _shared():\n"
        "    pass\n"
    ),
}


# ─── Unit: test_hook_returns_string_compact ──────────────────────────────────


class TestHookReturnsStringCompact:
    """AC1+AC2: FlowsHook.execute with detail=compact returns traces as str."""

    def test_hook_returns_string_compact(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, SIMPLE_PKG)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(ctx, entry="main", detail="compact")

        assert result.success is True
        assert "traces" in result.metadata
        traces = result.metadata["traces"]
        # MUST be a string, not a dict or list
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Content should come from format_flow_compact
        assert "main" in traces


# ─── Unit: test_hook_multi_entry_concatenated ────────────────────────────────


class TestHookMultiEntryConcatenated:
    """AC1: Multi-entry compact returns single string with headers per entry."""

    def test_hook_multi_entry_concatenated(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(tmp_path, MULTI_ENTRY_PKG)
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(
            ctx,
            entry="alpha\nbeta\ngamma",
            detail="compact",
        )

        assert result.success is True
        traces = result.metadata["traces"]
        # MUST be a single concatenated string
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Must contain header for each entry point
        assert "alpha" in traces
        assert "beta" in traces
        assert "gamma" in traces


# ─── Edge: empty flow ────────────────────────────────────────────────────────


class TestHookCompactEmptyFlow:
    """Edge: no entry points found → empty string or skip message."""

    def test_empty_flow_returns_empty_string(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": "x = 1\n",
            },
        )
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        # No entry points in this package
        result = hook.execute(ctx, detail="compact")

        assert result.success is True
        traces = result.metadata["traces"]
        # Should be a string (empty or skip message), not a dict
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )


# ─── Edge: circular / recursive calls ───────────────────────────────────────


class TestHookCompactCircularCalls:
    """Edge: recursive function → truncated at max_depth, still returns string."""

    def test_circular_calls_returns_string(self, tmp_path: Path) -> None:
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "main.py": (
                    "def func_a():\n    func_b()\n\ndef func_b():\n    func_a()\n"
                ),
            },
        )
        hook = FlowsHook()
        ctx: dict[str, Any] = {"working_dir": str(pkg_path)}
        result = hook.execute(
            ctx,
            entry="func_a",
            detail="compact",
            max_depth=5,
        )

        assert result.success is True
        traces = result.metadata["traces"]
        # Must be string, not dict
        assert isinstance(traces, str), (
            f"Expected traces to be str, got {type(traces).__name__}"
        )
        # Should contain the entry point
        assert "func_a" in traces
