"""Tests for trace_flow refactoring — extracted helpers and edge cases (AXM-891).

Unit tests validate the behavior of helper functions extracted from trace_flow
to reduce cyclomatic complexity. Edge cases cover boundary conditions.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.flows import build_callee_index, trace_flow
from axm_ast.models.calls import CallSite

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


# ─── Unit: _get_callees behavior ─────────────────────────────────────────────


class TestGetCallees:
    """Verify callee retrieval with and without a pre-built index."""

    def test_get_callees_with_index(self, tmp_path: Path) -> None:
        """Pre-built callee_index dict → BFS uses index lookup result."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def alpha():\n    return beta()\n\ndef beta():\n    return 42\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        index = build_callee_index(pkg)
        steps_with_index = trace_flow(pkg, "alpha", callee_index=index)
        steps_without_index = trace_flow(pkg, "alpha")
        # Both paths must produce the same result
        with_names = [s.name for s in steps_with_index]
        without_names = [s.name for s in steps_without_index]
        assert with_names == without_names
        assert "beta" in {s.name for s in steps_with_index}

    def test_get_callees_without_index(self, tmp_path: Path) -> None:
        """No index, real PackageInfo → falls back to find_callees."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def start():\n    return helper()\n\ndef helper():\n    return 1\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "start")
        step_names = [s.name for s in steps]
        assert step_names == ["start", "helper"]


# ─── Unit: _process_local_callees behavior ───────────────────────────────────


class TestProcessLocalCallees:
    """Verify local callee filtering and deduplication."""

    def test_process_local_callees_filters_stdlib(self, tmp_path: Path) -> None:
        """CallSite with `len` → not added to steps (stdlib filtered)."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def compute(items):\n"
                    "    n = len(items)\n"
                    "    return format_output(n)\n\n"
                    "def format_output(n):\n"
                    "    return str(n)\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "compute")
        step_names = {s.name for s in steps}
        assert "len" not in step_names
        assert "format_output" in step_names

    def test_process_local_callees_skips_visited(self, tmp_path: Path) -> None:
        """Already-visited symbol → not duplicated in steps."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def entry():\n"
                    "    a()\n"
                    "    b()\n\n"
                    "def a():\n"
                    "    shared()\n\n"
                    "def b():\n"
                    "    shared()\n\n"
                    "def shared():\n"
                    "    pass\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "entry", max_depth=3)
        # shared() called by both a() and b(), but should appear only once
        shared_steps = [s for s in steps if s.name == "shared"]
        assert len(shared_steps) == 1


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestTraceFlowEdgeCases:
    """Boundary conditions for trace_flow."""

    def test_entry_point_not_found(self, tmp_path: Path) -> None:
        """_find_symbol_location returns None → empty list returned."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def existing():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "nonexistent_function")
        assert steps == []

    def test_empty_callees(self, tmp_path: Path) -> None:
        """Function with no calls → only entry FlowStep."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def leaf():\n    return 42\n",
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "leaf")
        assert len(steps) == 1
        assert steps[0].name == "leaf"
        assert steps[0].depth == 0

    def test_all_callees_are_stdlib(self, tmp_path: Path) -> None:
        """exclude_stdlib=True with only builtins → only entry FlowStep."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": (
                    "def only_stdlib(items):\n"
                    "    n = len(items)\n"
                    "    t = type(n)\n"
                    "    return isinstance(t, int)\n"
                ),
            },
        )
        pkg = analyze_package(pkg_path)
        steps = trace_flow(pkg, "only_stdlib", exclude_stdlib=True)
        assert len(steps) == 1
        assert steps[0].name == "only_stdlib"

    def test_callee_index_miss(self, tmp_path: Path) -> None:
        """Key not in index → empty list, no error."""
        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "core.py": "def lonely():\n    pass\n",
            },
        )
        pkg = analyze_package(pkg_path)
        # Provide an empty index — all lookups will miss
        empty_index: dict[tuple[str, str], list[CallSite]] = {}
        steps = trace_flow(pkg, "lonely", callee_index=empty_index)
        # Entry point still appears, just no children
        assert len(steps) == 1
        assert steps[0].name == "lonely"
