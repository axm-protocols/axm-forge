from __future__ import annotations

from typing import Any

import pytest

from axm_ast.tools.flows_text import (
    render_compact_text,
    render_entry_points_text,
    render_source_text,
    render_trace_text,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_module_entries() -> list[dict[str, Any]]:
    """5 entries across 2 modules."""
    return [
        {
            "name": "alpha",
            "module": "pkg.mod_a",
            "kind": "export",
            "line": 10,
            "framework": "all",
        },
        {
            "name": "beta",
            "module": "pkg.mod_a",
            "kind": "export",
            "line": 20,
            "framework": "all",
        },
        {
            "name": "gamma",
            "module": "pkg.mod_a",
            "kind": "export",
            "line": 30,
            "framework": "all",
        },
        {
            "name": "delta",
            "module": "pkg.mod_b",
            "kind": "export",
            "line": 5,
            "framework": "all",
        },
        {
            "name": "epsilon",
            "module": "pkg.mod_b",
            "kind": "export",
            "line": 15,
            "framework": "all",
        },
    ]


@pytest.fixture
def three_depth_steps() -> list[dict[str, Any]]:
    """3 steps at depth 0, 1, 2."""
    return [
        {
            "name": "root",
            "module": "pkg.core",
            "line": 10,
            "depth": 0,
            "chain": ["root"],
        },
        {
            "name": "child",
            "module": "pkg.core",
            "line": 20,
            "depth": 1,
            "chain": ["root", "child"],
        },
        {
            "name": "grandchild",
            "module": "pkg.core",
            "line": 30,
            "depth": 2,
            "chain": ["root", "child", "grandchild"],
        },
    ]


# ---------------------------------------------------------------------------
# Entry-points rendering
# ---------------------------------------------------------------------------


class TestRenderEntryPointsText:
    def test_groups_by_module(self, two_module_entries: list[dict[str, Any]]) -> None:
        """Output has 2 module lines, entries inline."""
        text = render_entry_points_text(two_module_entries, count=5)
        # Both modules must appear as group keys
        assert "pkg.mod_a" in text
        assert "pkg.mod_b" in text
        # Entries from each module present
        assert "alpha" in text
        assert "delta" in text

    def test_elides_defaults(self) -> None:
        """Entry with line=1 and framework=all -> bare name (no :LINE)."""
        entries = [
            {
                "name": "foo",
                "module": "pkg.m",
                "kind": "export",
                "line": 1,
                "framework": "all",
            },
        ]
        text = render_entry_points_text(entries, count=1)
        # Should NOT contain ":1" suffix for line=1 default
        assert "foo" in text
        assert "foo:1" not in text

    def test_shows_decorators(self) -> None:
        """Entry with kind=decorator, framework=cyclopts -> @cyclopts name:LINE."""
        entries = [
            {
                "name": "serve",
                "module": "pkg.cli",
                "kind": "decorator",
                "line": 42,
                "framework": "cyclopts",
            },
        ]
        text = render_entry_points_text(entries, count=1)
        assert "@cyclopts" in text
        assert "serve:42" in text

    def test_shows_main_guard(self) -> None:
        """Entry with kind=main_guard -> ▶name:LINE."""
        entries = [
            {
                "name": "__main__",
                "module": "pkg.run",
                "kind": "main_guard",
                "line": 100,
                "framework": "main",
            },
        ]
        text = render_entry_points_text(entries, count=1)
        assert "\u25b6" in text  # ▶
        assert "__main__:100" in text

    def test_empty_entry_points(self) -> None:
        """Package with no exports -> header shows 0 entries."""
        text = render_entry_points_text([], count=0)
        assert "0 entries" in text
        assert "ast_flows" in text


# ---------------------------------------------------------------------------
# Trace rendering
# ---------------------------------------------------------------------------


class TestRenderTraceText:
    def test_indentation(self, three_depth_steps: list[dict[str, Any]]) -> None:
        """Steps at depth 0, 1, 2 have 0, 2, 4 leading spaces."""
        text = render_trace_text(
            entry="root",
            steps=three_depth_steps,
            depth=2,
            cross_module=False,
            count=3,
            truncated=False,
        )
        lines = text.strip().splitlines()
        # Find lines containing step names (skip header)
        step_lines = [
            line
            for line in lines
            if "root" in line or "child" in line or "grandchild" in line
        ]
        assert len(step_lines) >= 3
        # depth-0 line: 0 leading spaces
        root_line = next(
            line
            for line in step_lines
            if "root" in line and "grandchild" not in line and "child" not in line
        )
        assert root_line == root_line.lstrip()  # no leading spaces
        # depth-1 line: 2 leading spaces
        child_line = next(
            line for line in step_lines if "child" in line and "grandchild" not in line
        )
        assert child_line.startswith("  ") and not child_line.startswith("    ")
        # depth-2 line: 4 leading spaces
        gc_line = next(line for line in step_lines if "grandchild" in line)
        assert gc_line.startswith("    ") and not gc_line.startswith("      ")

    def test_no_chain(self, three_depth_steps: list[dict[str, Any]]) -> None:
        """Chain arrays should NOT appear in output."""
        text = render_trace_text(
            entry="root",
            steps=three_depth_steps,
            depth=2,
            cross_module=False,
            count=3,
            truncated=False,
        )
        assert "chain" not in text.lower()

    def test_header(self) -> None:
        """cross_module=True, count=42 -> header contains both."""
        steps = [
            {"name": f"s{i}", "module": "m", "line": i, "depth": 0, "chain": []}
            for i in range(42)
        ]
        text = render_trace_text(
            entry="s0",
            steps=steps,
            depth=5,
            cross_module=True,
            count=42,
            truncated=False,
        )
        header = text.splitlines()[0]
        assert "cross_module" in header
        assert "42" in header
        assert "steps" in header

    def test_truncated_header(self) -> None:
        """truncated=True -> header shows truncated."""
        steps = [{"name": "x", "module": "m", "line": 1, "depth": 0, "chain": []}]
        text = render_trace_text(
            entry="x",
            steps=steps,
            depth=5,
            cross_module=False,
            count=1,
            truncated=True,
        )
        header = text.splitlines()[0]
        assert "truncated" in header

    def test_single_step(self) -> None:
        """Entry with no callees -> one line at depth 0."""
        steps = [
            {
                "name": "lonely",
                "module": "pkg.m",
                "line": 7,
                "depth": 0,
                "chain": ["lonely"],
            }
        ]
        text = render_trace_text(
            entry="lonely",
            steps=steps,
            depth=0,
            cross_module=False,
            count=1,
            truncated=False,
        )
        body_lines = [
            line
            for line in text.strip().splitlines()
            if line and not line.startswith("ast_flows")
        ]
        # Filter to non-empty body lines
        body_lines = [line for line in body_lines if line.strip()]
        assert len(body_lines) == 1
        assert "lonely" in body_lines[0]

    def test_resolved_module(self) -> None:
        """Cross-module step shows resolved_module suffix."""
        steps = [
            {"name": "fn", "module": "pkg.a", "line": 1, "depth": 0, "chain": []},
            {
                "name": "ext",
                "module": "pkg.a",
                "line": 5,
                "depth": 1,
                "chain": [],
                "resolved_module": "other.mod",
            },
        ]
        text = render_trace_text(
            entry="fn",
            steps=steps,
            depth=1,
            cross_module=True,
            count=2,
            truncated=False,
        )
        assert "other.mod" in text


# ---------------------------------------------------------------------------
# Compact rendering
# ---------------------------------------------------------------------------


class TestRenderCompactText:
    def test_header_prepend(self) -> None:
        """compact string with count=10 -> output starts with header, then compact."""
        compact = "root\n├── child_a\n└── child_b"
        text = render_compact_text(
            entry="root",
            compact=compact,
            depth=1,
            cross_module=False,
            count=10,
            truncated=False,
        )
        lines = text.splitlines()
        # First line is header
        assert lines[0].startswith("ast_flows")
        assert "10" in lines[0]
        # Compact content follows
        remaining = "\n".join(lines[1:]).strip()
        assert compact in remaining


# ---------------------------------------------------------------------------
# Source rendering
# ---------------------------------------------------------------------------


class TestRenderSourceText:
    def test_source_inline_blocks(self) -> None:
        """Step with source -> source appears indented below node line."""
        steps = [
            {
                "name": "myfunc",
                "module": "pkg.core",
                "line": 10,
                "depth": 0,
                "chain": [],
                "source": "def myfunc():\n    return 42",
            },
        ]
        text = render_source_text(
            entry="myfunc",
            steps=steps,
            depth=0,
            cross_module=False,
            count=1,
            truncated=False,
        )
        assert "myfunc" in text
        assert "def myfunc" in text
        assert "return 42" in text

    def test_no_source(self) -> None:
        """Step without source -> just node line, no code block."""
        steps = [
            {"name": "bare", "module": "pkg.core", "line": 5, "depth": 0, "chain": []},
        ]
        text = render_source_text(
            entry="bare",
            steps=steps,
            depth=0,
            cross_module=False,
            count=1,
            truncated=False,
        )
        assert "bare" in text
        # Only the node line, no source block
        body_lines = [
            line
            for line in text.strip().splitlines()
            if line.strip() and not line.startswith("ast_flows")
        ]
        assert len(body_lines) == 1
