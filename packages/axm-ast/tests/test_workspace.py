"""Tests for workspace multi-package support.

Covers: detection, analysis, cross-package callers, impact,
context, dep graph, mermaid formatting, and edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.workspace import (
    _find_package_source,
    _parse_member_deps,
    _parse_workspace_members,
    analyze_workspace,
    build_workspace_context,
    build_workspace_dep_graph,
    detect_workspace,
    format_workspace_graph_mermaid,
)
from axm_ast.models.nodes import WorkspaceInfo

# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_pyproject(path: Path, name: str, deps: list[str] | None = None) -> None:
    """Write a minimal pyproject.toml for a workspace member."""
    dep_lines = ""
    if deps:
        dep_strs = ", ".join(f'"{d}"' for d in deps)
        dep_lines = f"dependencies = [{dep_strs}]"
    else:
        dep_lines = "dependencies = []"

    path.write_text(
        f"""\
[project]
name = "{name}"
version = "0.1.0"
{dep_lines}
""",
        encoding="utf-8",
    )


def _make_workspace(
    root: Path,
    members: list[str],
    *,
    ws_name: str = "test-workspace",
) -> None:
    """Create a workspace root pyproject.toml."""
    member_strs = ", ".join(f'"{m}"' for m in members)
    (root / "pyproject.toml").write_text(
        f"""\
[project]
name = "{ws_name}"
version = "0.1.0"

[tool.uv.workspace]
members = [{member_strs}]
""",
        encoding="utf-8",
    )


def _make_member_package(
    root: Path,
    member_name: str,
    *,
    src_layout: bool = True,
    deps: list[str] | None = None,
    py_files: dict[str, str] | None = None,
) -> Path:
    """Create a workspace member with a source package.

    Returns the path to the member directory.
    """
    member_dir = root / member_name
    member_dir.mkdir(parents=True, exist_ok=True)

    # pyproject.toml
    _make_pyproject(member_dir / "pyproject.toml", member_name, deps)

    # Package name = member_name with dashes replaced by underscores
    pkg_name = member_name.replace("-", "_")

    if src_layout:
        pkg_dir = member_dir / "src" / pkg_name
    else:
        pkg_dir = member_dir / pkg_name

    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    if py_files:
        for fname, content in py_files.items():
            (pkg_dir / fname).write_text(content, encoding="utf-8")

    return member_dir


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    """Create a 2-package workspace with cross-package calls."""
    _make_workspace(tmp_path, ["pkg-a", "pkg-b"])

    # pkg-a: defines a function `helper()`
    _make_member_package(
        tmp_path,
        "pkg-a",
        py_files={
            "core.py": 'def helper():\n    """A helper function."""\n    return 42\n',
        },
    )

    # pkg-b: calls `helper()` from pkg-a
    pkg_b_main = "from pkg_a.core import helper\n\ndef run():\n    return helper()\n"
    _make_member_package(
        tmp_path,
        "pkg-b",
        deps=["pkg-a"],
        py_files={
            "main.py": pkg_b_main,
        },
    )

    return tmp_path


# ─── Detection Tests ────────────────────────────────────────────────────────


class TestDetectWorkspace:
    """Tests for workspace detection."""

    def test_detect_workspace_uv(self, workspace_root: Path) -> None:
        """Detect a valid uv workspace."""
        ws = detect_workspace(workspace_root)
        assert ws is not None
        assert isinstance(ws, WorkspaceInfo)
        assert ws.name == "test-workspace"
        assert ws.root == workspace_root

    def test_detect_workspace_none_regular_project(self, tmp_path: Path) -> None:
        """Regular project without workspace section returns None."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "regular"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        assert detect_workspace(tmp_path) is None

    def test_detect_workspace_no_pyproject(self, tmp_path: Path) -> None:
        """Directory without pyproject.toml returns None."""
        assert detect_workspace(tmp_path) is None

    def test_detect_workspace_empty_members(self, tmp_path: Path) -> None:
        """Workspace with empty members list returns None."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\n\n[tool.uv.workspace]\nmembers = []\n',
            encoding="utf-8",
        )
        assert detect_workspace(tmp_path) is None


# ─── Parsing Tests ───────────────────────────────────────────────────────────


class TestParsing:
    """Tests for pyproject.toml parsing helpers."""

    def test_parse_workspace_members(self) -> None:
        text = '[tool.uv.workspace]\nmembers = ["pkg-a", "pkg-b"]'
        assert _parse_workspace_members(text) == ["pkg-a", "pkg-b"]

    def test_parse_workspace_members_multiline(self) -> None:
        text = '[tool.uv.workspace]\nmembers = [\n  "alpha",\n  "beta",\n]'
        assert _parse_workspace_members(text) == ["alpha", "beta"]

    def test_parse_workspace_members_no_section(self) -> None:
        text = '[project]\nname = "foo"'
        assert _parse_workspace_members(text) == []

    def test_parse_member_deps(self, tmp_path: Path) -> None:
        _make_pyproject(tmp_path / "pyproject.toml", "test", ["dep-a>=1.0", "dep-b"])
        deps = _parse_member_deps(tmp_path)
        assert "dep-a" in deps
        assert "dep-b" in deps

    def test_parse_member_deps_no_pyproject(self, tmp_path: Path) -> None:
        assert _parse_member_deps(tmp_path) == []

    def test_find_package_source_src_layout(self, workspace_root: Path) -> None:
        member = workspace_root / "pkg-a"
        src = _find_package_source(member)
        assert src is not None
        assert src.name == "pkg_a"

    def test_find_package_source_flat_layout(self, tmp_path: Path) -> None:
        member = tmp_path / "flat-pkg"
        member.mkdir()
        pkg_dir = member / "flat_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        src = _find_package_source(member)
        assert src is not None
        assert src.name == "flat_pkg"

    def test_find_package_source_not_found(self, tmp_path: Path) -> None:
        member = tmp_path / "empty-member"
        member.mkdir()
        assert _find_package_source(member) is None


# ─── Workspace Analysis Tests ───────────────────────────────────────────────


class TestAnalyzeWorkspace:
    """Tests for workspace analysis."""

    def test_analyze_workspace_parses_all(self, workspace_root: Path) -> None:
        """Analyze workspace finds both packages."""
        ws = analyze_workspace(workspace_root)
        assert len(ws.packages) == 2
        pkg_names = {p.name for p in ws.packages}
        assert "pkg_a" in pkg_names
        assert "pkg_b" in pkg_names

    def test_analyze_workspace_has_modules(self, workspace_root: Path) -> None:
        """Each package has the expected modules."""
        ws = analyze_workspace(workspace_root)
        for pkg in ws.packages:
            assert len(pkg.modules) > 0

    def test_analyze_workspace_not_workspace(self, tmp_path: Path) -> None:
        """Raises ValueError for non-workspace path."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "single"\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="not a uv workspace"):
            analyze_workspace(tmp_path)

    def test_workspace_dep_graph(self, workspace_root: Path) -> None:
        """Package dependency graph has correct edge."""
        ws = analyze_workspace(workspace_root)
        graph = build_workspace_dep_graph(ws)
        assert "pkg-b" in graph
        assert "pkg-a" in graph["pkg-b"]

    def test_workspace_dep_graph_no_edges(self, tmp_path: Path) -> None:
        """Workspace without inter-package deps has empty graph."""
        _make_workspace(tmp_path, ["alpha", "beta"])
        _make_member_package(tmp_path, "alpha")
        _make_member_package(tmp_path, "beta")
        ws = analyze_workspace(tmp_path)
        graph = build_workspace_dep_graph(ws)
        assert graph == {}


# ─── Cross-Package Callers ───────────────────────────────────────────────────


class TestCrossPackageCallers:
    """Tests for find_callers_workspace."""

    def test_find_callers_workspace(self, workspace_root: Path) -> None:
        """Find cross-package call to helper()."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "helper")

        # Should find the call in pkg_b::main
        assert len(callers) >= 1
        modules = [c.module for c in callers]
        assert any("pkg_b::" in m for m in modules)

    def test_find_callers_workspace_no_match(self, workspace_root: Path) -> None:
        """Symbol not called anywhere returns empty list."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "nonexistent_function")
        assert callers == []

    def test_find_callers_workspace_prefix_format(self, workspace_root: Path) -> None:
        """Module names use pkg_name::module_name format."""
        from axm_ast.core.callers import find_callers_workspace

        ws = analyze_workspace(workspace_root)
        callers = find_callers_workspace(ws, "helper")
        for c in callers:
            assert "::" in c.module


# ─── Workspace Impact ────────────────────────────────────────────────────────


class TestWorkspaceImpact:
    """Tests for analyze_impact_workspace."""

    def test_analyze_impact_workspace(self, workspace_root: Path) -> None:
        """Impact analysis finds cross-package callers."""
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_root, "helper")
        assert result["symbol"] == "helper"
        assert result["workspace"] == "test-workspace"
        assert "definition" in result
        assert "callers" in result
        assert "score" in result

    def test_analyze_impact_workspace_callers(self, workspace_root: Path) -> None:
        """Impact callers include cross-package references."""
        from axm_ast.core.impact import analyze_impact_workspace

        result = analyze_impact_workspace(workspace_root, "helper")
        caller_modules = [c["module"] for c in result["callers"]]
        assert any("pkg_b::" in m for m in caller_modules)


# ─── Workspace Context ──────────────────────────────────────────────────────


class TestWorkspaceContext:
    """Tests for build_workspace_context."""

    def test_build_workspace_context(self, workspace_root: Path) -> None:
        """Context returns workspace-level info."""
        ctx = build_workspace_context(workspace_root)
        assert ctx["workspace"] == "test-workspace"
        assert ctx["package_count"] == 2
        assert len(ctx["packages"]) == 2

    def test_build_workspace_context_package_summaries(
        self, workspace_root: Path
    ) -> None:
        """Package summaries have expected fields."""
        ctx = build_workspace_context(workspace_root)
        for pkg in ctx["packages"]:
            assert "name" in pkg
            assert "module_count" in pkg
            assert "function_count" in pkg
            assert "class_count" in pkg

    def test_build_workspace_context_graph(self, workspace_root: Path) -> None:
        """Context includes package dependency graph."""
        ctx = build_workspace_context(workspace_root)
        assert "package_graph" in ctx
        assert "pkg-b" in ctx["package_graph"]


# ─── Mermaid Formatting ─────────────────────────────────────────────────────


class TestMermaidFormatting:
    """Tests for workspace mermaid graph output."""

    def test_format_workspace_graph_mermaid(self, workspace_root: Path) -> None:
        """Mermaid output has expected structure."""
        ws = analyze_workspace(workspace_root)
        mermaid = format_workspace_graph_mermaid(ws)
        assert "graph TD" in mermaid
        assert "pkg_b --> pkg_a" in mermaid


# ─── Edge Cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests for workspace features."""

    def test_missing_member_skipped(self, tmp_path: Path) -> None:
        """Workspace member that doesn't exist is skipped gracefully."""
        _make_workspace(tmp_path, ["exists", "missing"])
        _make_member_package(tmp_path, "exists")
        # Don't create "missing" directory

        ws = analyze_workspace(tmp_path)
        assert len(ws.packages) == 1
        assert ws.packages[0].name == "exists"

    def test_member_without_src_flat_layout(self, tmp_path: Path) -> None:
        """Member with flat layout (no src/) is still analyzed."""
        _make_workspace(tmp_path, ["flat-pkg"])
        _make_member_package(tmp_path, "flat-pkg", src_layout=False)

        ws = analyze_workspace(tmp_path)
        assert len(ws.packages) == 1
        assert ws.packages[0].name == "flat_pkg"

    def test_circular_workspace_deps(self, tmp_path: Path) -> None:
        """Circular deps between packages don't crash."""
        _make_workspace(tmp_path, ["circ-a", "circ-b"])
        _make_member_package(tmp_path, "circ-a", deps=["circ-b"])
        _make_member_package(tmp_path, "circ-b", deps=["circ-a"])

        ws = analyze_workspace(tmp_path)
        graph = build_workspace_dep_graph(ws)
        assert "circ-a" in graph
        assert "circ-b" in graph
        assert "circ-b" in graph["circ-a"]
        assert "circ-a" in graph["circ-b"]

    def test_single_member_workspace(self, tmp_path: Path) -> None:
        """Single-member workspace still works."""
        _make_workspace(tmp_path, ["only-pkg"])
        _make_member_package(tmp_path, "only-pkg")

        ws = analyze_workspace(tmp_path)
        assert len(ws.packages) == 1

    def test_member_without_python_source(self, tmp_path: Path) -> None:
        """Member without any Python package is skipped."""
        _make_workspace(tmp_path, ["no-python"])
        member_dir = tmp_path / "no-python"
        member_dir.mkdir()
        _make_pyproject(member_dir / "pyproject.toml", "no-python")
        # No src/ or package directory with __init__.py

        ws = analyze_workspace(tmp_path)
        assert len(ws.packages) == 0
