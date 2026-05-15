from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.graph import GraphTool


@pytest.fixture
def graph_tool() -> GraphTool:
    return GraphTool()


@pytest.fixture
def fake_workspace():
    """Workspace with two packages and one dependency edge."""
    ws = SimpleNamespace(
        packages=[
            SimpleNamespace(name="axm-alpha"),
            SimpleNamespace(name="axm-beta"),
        ],
        package_edges=[("axm-alpha", "axm-beta")],
    )
    graph = {"axm-alpha": ["axm-beta"]}
    return ws, graph


def test_workspace_graph_text_format(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """_execute_workspace format='text' returns data['text'] with Nodes: and Edges:."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="text")

    assert result.success is True
    text = result.data["text"]
    assert isinstance(text, str)
    assert "Nodes:" in text
    assert "Edges:" in text


def test_workspace_graph_text_contains_packages(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Text output lists known package names."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="text")

    text = result.data["text"]
    assert "axm-alpha" in text
    assert "axm-beta" in text


class TestGraphToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: GraphTool) -> None:
        assert tool.name == "ast_graph"


class TestGraphEdgeCasesUnit:
    """Edge cases for GraphTool (no I/O)."""

    def test_bad_path(self, tool: GraphTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()
