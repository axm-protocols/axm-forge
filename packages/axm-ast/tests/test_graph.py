"""Tests for GraphTool — import dependency graph via MCP tool wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.graph import GraphTool


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()


@pytest.fixture()
def graph_pkg(tmp_path: Path) -> Path:
    """Create a package with internal imports for graph tests."""
    pkg = tmp_path / "graphdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Graph demo."""\n\nfrom .core import main\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\nfrom .utils import helper\n\n\n'
        "def main() -> str:\n"
        '    """Entry point."""\n'
        "    return helper()\n"
    )
    (pkg / "utils.py").write_text(
        '"""Utils module."""\n\n\n'
        "def helper() -> str:\n"
        '    """Help."""\n'
        '    return "ok"\n'
    )
    return pkg


# ─── Tool identity ──────────────────────────────────────────────────────────


class TestGraphToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: GraphTool) -> None:
        assert tool.name == "ast_graph"


# ─── JSON format ─────────────────────────────────────────────────────────────


class TestGraphJSON:
    """Tests for default JSON format output."""

    def test_returns_graph_dict(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg))
        assert result.success is True
        assert "graph" in result.data
        assert isinstance(result.data["graph"], dict)

    def test_graph_has_edges(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg))
        graph = result.data["graph"]
        # core imports utils, __init__ imports core
        all_targets = []
        for targets in graph.values():
            all_targets.extend(targets)
        assert len(all_targets) >= 1


# ─── Mermaid format ──────────────────────────────────────────────────────────


class TestGraphMermaid:
    """Tests for mermaid format output."""

    def test_mermaid_returns_string(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert isinstance(result.data["mermaid"], str)

    def test_mermaid_contains_graph_keyword(
        self, tool: GraphTool, graph_pkg: Path
    ) -> None:
        result = tool.execute(path=str(graph_pkg), format="mermaid")
        mermaid_lower = result.data["mermaid"].lower()
        assert "graph" in mermaid_lower or "flowchart" in mermaid_lower


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestGraphEdgeCases:
    """Edge cases for GraphTool."""

    def test_bad_path(self, tool: GraphTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False

    def test_empty_package(self, tool: GraphTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert isinstance(result.data["graph"], dict)

    def test_no_internal_imports(self, tool: GraphTool, tmp_path: Path) -> None:
        """Package with no internal imports → empty graph."""
        pkg = tmp_path / "noimports"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""No imports."""\n')
        (pkg / "a.py").write_text("x = 1\n")
        (pkg / "b.py").write_text("y = 2\n")
        result = tool.execute(path=str(pkg))
        assert result.success is True
        graph = result.data["graph"]
        total_edges = sum(len(v) for v in graph.values())
        assert total_edges == 0
