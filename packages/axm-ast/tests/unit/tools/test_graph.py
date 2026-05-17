"""Unit and functional tests for GraphTool."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.graph import GraphTool

AXM_AST_PATH = str(
    Path(__file__).resolve().parents[3]  # tests/unit/tools/.. -> axm-ast root
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()


@pytest.fixture
def graph_tool() -> GraphTool:
    return GraphTool()


@pytest.fixture()
def tool__from_graph_execute_refactor() -> GraphTool:
    return GraphTool()


@pytest.fixture
def fake_workspace_no_deps() -> tuple[SimpleNamespace, dict[str, list[str]]]:
    """Workspace where packages have no inter-package dependencies."""
    ws = SimpleNamespace(
        packages=[
            SimpleNamespace(name="axm-solo"),
            SimpleNamespace(name="axm-lone"),
        ],
        package_edges=[],
    )
    graph: dict[str, list[str]] = {}
    return ws, graph


@pytest.fixture
def render() -> Callable[..., str]:
    """Shortcut to the staticmethod under test."""
    return GraphTool._render_pkg_text


@pytest.fixture
def pkg_nodes_with_edges() -> list[str]:
    return ["cli", "core.parser", "core.cache", "utils"]


@pytest.fixture
def pkg_graph_with_edges() -> dict[str, list[str]]:
    return {"cli": ["core.parser"], "core.parser": ["utils"]}


@pytest.fixture
def pkg_nodes_no_edges() -> list[str]:
    return ["cli", "core", "utils"]


@pytest.fixture
def pkg_graph_no_edges() -> dict[str, list[str]]:
    return {}


# ---------------------------------------------------------------------------
# Tool identity
# ---------------------------------------------------------------------------


class TestGraphToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: GraphTool) -> None:
        assert tool.name == "ast_graph"


# ---------------------------------------------------------------------------
# Bad path / invalid input
# ---------------------------------------------------------------------------


class TestGraphEdgeCasesUnit:
    """Edge cases for GraphTool (no I/O)."""

    def test_bad_path(self, tool: GraphTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


class TestGraphEdgeCasesRefactorUnit:
    """Edge cases from test_spec (unit, no I/O)."""

    def test_invalid_path(self, tool__from_graph_execute_refactor: GraphTool) -> None:
        """Non-existent directory returns ToolResult(success=False)."""
        result = tool__from_graph_execute_refactor.execute(
            path="/nonexistent/surely/missing"
        )
        assert result.success is False
        assert result.error


# ---------------------------------------------------------------------------
# Workspace-level _execute_workspace
# ---------------------------------------------------------------------------


def test_workspace_graph_text_no_deps(
    graph_tool: GraphTool,
    fake_workspace_no_deps: tuple[SimpleNamespace, dict[str, list[str]]],
) -> None:
    """Workspace with no inter-package deps shows nodes but empty Edges section."""
    ws, graph = fake_workspace_no_deps
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="text")

    text = result.data["text"]
    assert "Nodes:" in text
    assert "axm-solo" in text
    assert "axm-lone" in text
    # Edges header present but no arrows after it
    edges_section = text.split("Edges:")[1]
    assert "->" not in edges_section


def test_workspace_single_package(graph_tool: GraphTool) -> None:
    """Single-package workspace must return nodes with exactly one element."""
    ws = SimpleNamespace(
        packages=[SimpleNamespace(name="solo-pkg")],
        package_edges=[],
    )
    graph: dict[str, list[str]] = {}
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="json")

    assert result.data["nodes"] == ["solo-pkg"]


# ---------------------------------------------------------------------------
# Unit tests — _render_pkg_text (basic shape + grouping + mermaid)
# ---------------------------------------------------------------------------


def test_render_pkg_text_basic(render: Callable[..., str]) -> None:
    """3 modules, 2 edges, no mermaid -> Header + Modules + Edges sections."""
    nodes = ["api", "core", "utils"]
    graph = {"api": ["core"], "core": ["utils"]}

    result = render("my_pkg", nodes, graph, mermaid_str=None)

    assert "ast_graph | my_pkg" in result
    assert "3 modules · 2 edges" in result
    assert "Modules:" in result
    assert "  api" in result
    assert "  core" in result
    assert "  utils" in result
    assert "Edges:" in result
    assert "  api → core" in result
    assert "  core → utils" in result
    assert "mermaid" not in result


def test_render_pkg_text_grouped(render: Callable[..., str]) -> None:
    """Modules with dotted names grouped under prefix."""
    nodes = ["core.parser", "core.cache", "utils"]
    graph: dict[str, list[str]] = {}

    result = render("my_pkg", nodes, graph, mermaid_str=None)

    assert "Modules:" in result
    # standalone
    assert "  utils" in result
    # grouped
    assert "  core: parser cache" in result


def test_render_pkg_text_mermaid(render: Callable[..., str]) -> None:
    """Graph with edges + mermaid string -> Mermaid block appended."""
    nodes = ["a", "b"]
    graph = {"a": ["b"]}
    mermaid = "graph LR\n  a --> b"

    result = render("pkg", nodes, graph, mermaid_str=mermaid)

    assert "```mermaid" in result
    assert mermaid in result
    assert result.endswith("```")


def test_render_pkg_text_no_edges_simple(render: Callable[..., str]) -> None:
    """Modules only, empty graph -> No Edges section, no mermaid."""
    nodes = ["alpha", "beta"]
    graph: dict[str, list[str]] = {}

    result = render("pkg", nodes, graph, mermaid_str=None)

    assert "0 edges" in result
    assert "Edges:" not in result
    assert "mermaid" not in result


def test_render_pkg_text_single_module(render: Callable[..., str]) -> None:
    """1 node, 0 edges -> singular 'module' label."""
    nodes = ["only"]
    graph: dict[str, list[str]] = {}

    result = render("pkg", nodes, graph, mermaid_str=None)

    assert "1 module · 0 edges" in result


def test_render_pkg_text_empty_graph_with_mermaid(render: Callable[..., str]) -> None:
    """mermaid_str provided but graph={} -> Mermaid block suppressed."""
    nodes = ["a"]
    graph: dict[str, list[str]] = {}
    mermaid = "graph LR\n  a"

    result = render("pkg", nodes, graph, mermaid_str=mermaid)

    assert "mermaid" not in result


# ---------------------------------------------------------------------------
# Unit tests — _render_pkg_text (with fixtures, grouped layout)
# ---------------------------------------------------------------------------


class TestRenderPkgText:
    def test_render_pkg_text_with_edges(
        self,
        pkg_nodes_with_edges: list[str],
        pkg_graph_with_edges: dict[str, list[str]],
    ) -> None:
        text = GraphTool._render_pkg_text(
            pkg_name="mypkg",
            nodes=pkg_nodes_with_edges,
            graph=pkg_graph_with_edges,
            mermaid_str=None,
        )
        # Header
        assert "4 modules" in text
        assert "2 edges" in text
        # Tree-grouped modules: core groups parser + cache
        assert "core:" in text
        assert "parser" in text
        assert "cache" in text
        # Edges section present with arrow notation
        assert "→" in text  # →

    def test_render_pkg_text_no_edges(
        self,
        pkg_nodes_no_edges: list[str],
        pkg_graph_no_edges: dict[str, list[str]],
    ) -> None:
        text = GraphTool._render_pkg_text(
            pkg_name="mypkg",
            nodes=pkg_nodes_no_edges,
            graph=pkg_graph_no_edges,
            mermaid_str=None,
        )
        # Header shows 0 edges
        assert "0 edges" in text
        # No Edges section after header
        lines_after_header = text.split("\n")[1:]
        assert not any(
            line.strip().lower().startswith("edges") for line in lines_after_header
        )

    def test_render_pkg_text_mermaid_no_edges(
        self,
        pkg_nodes_no_edges: list[str],
        pkg_graph_no_edges: dict[str, list[str]],
    ) -> None:
        text = GraphTool._render_pkg_text(
            pkg_name="mypkg",
            nodes=pkg_nodes_no_edges,
            graph=pkg_graph_no_edges,
            mermaid_str="graph LR\n",
        )
        # Mermaid suppressed for zero-edge graph
        assert "```mermaid" not in text

    def test_render_pkg_text_mermaid_with_edges(
        self,
        pkg_nodes_with_edges: list[str],
        pkg_graph_with_edges: dict[str, list[str]],
    ) -> None:
        mermaid = "graph LR\n  cli --> core.parser\n  core.parser --> utils"
        text = GraphTool._render_pkg_text(
            pkg_name="mypkg",
            nodes=pkg_nodes_with_edges,
            graph=pkg_graph_with_edges,
            mermaid_str=mermaid,
        )
        assert "```mermaid" in text
        assert mermaid in text


# ---------------------------------------------------------------------------
# Unit tests — _render_ws_text
# ---------------------------------------------------------------------------


class TestRenderWsText:
    def test_render_ws_text(self) -> None:
        graph = {"axm-engine": ["axm", "axm-nexus"]}
        text = GraphTool._render_ws_text(
            ws_name="myws",
            graph=graph,
            mermaid_str=None,
        )
        assert "workspace" in text
        assert "3 packages" in text
        assert "2 edges" in text
        assert "→" in text  # →
        assert "axm-engine" in text

    def test_render_ws_text_mermaid(self) -> None:
        graph = {"axm-engine": ["axm", "axm-nexus"]}
        mermaid = "graph LR\n  axm-engine --> axm\n  axm-engine --> axm-nexus"
        text = GraphTool._render_ws_text(
            ws_name="myws",
            graph=graph,
            mermaid_str=mermaid,
        )
        assert "```mermaid" in text
        assert mermaid in text


# ---------------------------------------------------------------------------
# Edge cases — render helpers
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_module_package(self) -> None:
        text = GraphTool._render_pkg_text(
            pkg_name="tiny",
            nodes=["main"],
            graph={},
            mermaid_str=None,
        )
        assert "1 module" in text
        assert "0 edges" in text
        assert "main" in text
        # No Edges section
        lines_after_header = text.split("\n")[1:]
        assert not any(
            line.strip().lower().startswith("edges") for line in lines_after_header
        )

    def test_deep_nesting(self) -> None:
        text = GraphTool._render_pkg_text(
            pkg_name="deep",
            nodes=["a.b.c.d.e", "a.b.x", "f"],
            graph={},
            mermaid_str=None,
        )
        # Groups by first-level prefix only
        assert "a:" in text
        assert "b.c.d.e" in text
        assert "b.x" in text
        assert "f" in text

    def test_empty_workspace_graph(self) -> None:
        text = GraphTool._render_ws_text(
            ws_name="empty",
            graph={},
            mermaid_str=None,
        )
        assert "0 edges" in text
        assert "0 packages" in text
        # No Dependencies section
        lines_after_header = text.split("\n")[1:]
        assert not any(
            line.strip().lower().startswith("dependencies")
            for line in lines_after_header
        )


# ---------------------------------------------------------------------------
# Functional tests — exercises real package via public execute()
# ---------------------------------------------------------------------------


@pytest.mark.functional()
def test_graph_tool_src_layout_has_edges() -> None:
    """GraphTool on axm-ast (src-layout) returns a graph with edges."""
    result = GraphTool().execute(path=AXM_AST_PATH)
    assert result.success, f"GraphTool failed: {result.error}"
    graph = result.data["graph"]
    has_edges = any(len(targets) > 0 for targets in graph.values())
    assert has_edges, "Expected at least one key with non-empty adjacency list"


@pytest.mark.functional()
def test_mermaid_src_layout_has_edges() -> None:
    """GraphTool mermaid output for src-layout contains edges."""
    result = GraphTool().execute(path=AXM_AST_PATH, format="mermaid")
    assert result.success, f"GraphTool failed: {result.error}"
    assert " --> " in result.data["mermaid"], "Mermaid output should contain edges"


# ---------------------------------------------------------------------------
# TestGraphToolUnit (from test_tools.py)
# ---------------------------------------------------------------------------


class TestGraphToolUnit:
    """Tests for ast_graph tool."""

    def test_has_name(self) -> None:
        tool_inst = GraphTool()
        assert tool_inst.name == "ast_graph"
