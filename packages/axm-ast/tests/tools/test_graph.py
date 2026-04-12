from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.graph import GraphTool

_NODE_DECL_RE = re.compile(r'^\s+(\w+)\[".*"\]', re.MULTILINE)
_EDGE_RE = re.compile(r"^\s+(\S+)\s+-->\s+(\S+)", re.MULTILINE)


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


# ---------- Unit tests ----------


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


# ---------- Functional tests ----------


def test_graph_tool_workspace_text(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Full execute path with workspace detection returns non-empty text."""
    ws, graph = fake_workspace
    with (
        patch.object(graph_tool, "_detect_workspace", return_value=True),
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool.execute(path="/fake", format="text")

    assert result.success is True
    assert result.data.get("text")
    assert len(result.data["text"]) > 0


def test_graph_tool_workspace_mermaid_valid(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Mermaid output: all edge node IDs are in declared node set."""
    ws, graph = fake_workspace
    with (
        patch.object(graph_tool, "_detect_workspace", return_value=True),
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool.execute(path="/fake", format="mermaid")

    assert result.success is True
    mermaid = result.data["mermaid"]
    declared = {m.group(1) for m in _NODE_DECL_RE.finditer(mermaid)}
    edge_ids: set[str] = set()
    for m in _EDGE_RE.finditer(mermaid):
        edge_ids.add(m.group(1))
        edge_ids.add(m.group(2))
    missing = edge_ids - declared
    assert not missing, f"Edge IDs not declared as nodes: {missing}\n{mermaid}"


# ---------- Edge cases ----------


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


def test_workspace_graph_unknown_format_falls_through(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Unknown format falls through to json (returns graph, no text/mermaid)."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="xml")

    assert result.success is True
    assert "graph" in result.data
    assert "text" not in result.data
    assert "mermaid" not in result.data
