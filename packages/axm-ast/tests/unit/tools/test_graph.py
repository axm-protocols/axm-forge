"""Unit tests for GraphTool (pure, no I/O)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.graph import GraphTool


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()


class TestGraphToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: GraphTool) -> None:
        assert tool.name == "ast_graph"


class TestGraphEdgeCasesUnit:
    """Edge cases for GraphTool (no I/O)."""

    def test_bad_path(self, tool: GraphTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


@pytest.fixture
def graph_tool() -> GraphTool:
    return GraphTool()


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


class TestGraphEdgeCasesRefactorUnit:
    """Edge cases from test_spec (unit, no I/O)."""

    def test_invalid_path(self, tool__from_graph_execute_refactor: GraphTool) -> None:
        """Non-existent directory returns ToolResult(success=False)."""
        result = tool__from_graph_execute_refactor.execute(
            path="/nonexistent/surely/missing"
        )
        assert result.success is False
        assert result.error


@pytest.fixture
def fake_workspace_no_deps():
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


@pytest.fixture()
def tool__from_graph_execute_refactor() -> GraphTool:
    return GraphTool()
