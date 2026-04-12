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


# ---------- Workspace nodes key (AXM-1361) ----------


def test_workspace_graph_has_nodes_key(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """_execute_workspace must return a 'nodes' key containing a list of strings."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="json")

    assert result.success is True
    assert "nodes" in result.data
    assert isinstance(result.data["nodes"], list)
    assert all(isinstance(n, str) for n in result.data["nodes"])


def test_workspace_nodes_includes_all_packages(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """nodes list must include every package in the workspace."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="json")

    expected = {p.name for p in ws.packages}
    assert len(result.data["nodes"]) == len(ws.packages)
    assert set(result.data["nodes"]) == expected


def test_graph_tool_schema_parity(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Both package and workspace execute results must have 'graph' and 'nodes' keys."""
    ws, ws_graph = fake_workspace

    # Workspace result
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            return_value=ws_graph,
        ),
    ):
        ws_result = graph_tool._execute_workspace(Path("/fake"), format="json")

    # Package result
    mod = SimpleNamespace(path=Path("src/mypkg/foo.py"))
    pkg = SimpleNamespace(root=Path("src/mypkg"), modules=[mod])
    pkg_graph: dict[str, list[str]] = {"mypkg.foo": []}
    with (
        patch("axm_ast.core.cache.get_package", return_value=pkg),
        patch("axm_ast.core.analyzer.build_import_graph", return_value=pkg_graph),
        patch("axm_ast.core.analyzer.module_dotted_name", return_value="mypkg.foo"),
    ):
        pkg_result = graph_tool._execute_package(Path("/fake"), format="json")

    for result in (ws_result, pkg_result):
        assert result.success is True
        assert "graph" in result.data, f"Missing 'graph' key in {result.data.keys()}"
        assert "nodes" in result.data, f"Missing 'nodes' key in {result.data.keys()}"


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


def test_workspace_mermaid_format_has_nodes(
    graph_tool: GraphTool, fake_workspace: tuple[SimpleNamespace, dict[str, list[str]]]
) -> None:
    """Mermaid format must still include the nodes key alongside mermaid key."""
    ws, graph = fake_workspace
    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch("axm_ast.core.workspace.build_workspace_dep_graph", return_value=graph),
        patch(
            "axm_ast.core.workspace.format_workspace_graph_mermaid",
            return_value="graph TD\nA --> B",
        ),
    ):
        result = graph_tool._execute_workspace(Path("/fake"), format="mermaid")

    assert result.success is True
    assert "mermaid" in result.data
    assert "nodes" in result.data
    assert set(result.data["nodes"]) == {"axm-alpha", "axm-beta"}
