from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_ast.tools.graph import GraphTool


def _make_pkg(
    root: Path, module_files: list[str], edges: list[tuple[str, str]]
) -> SimpleNamespace:
    """Build a minimal PackageInfo-like namespace for testing."""
    mods = [SimpleNamespace(path=root / f) for f in module_files]
    return SimpleNamespace(root=root, modules=mods, dependency_edges=edges)


@pytest.fixture
def tool():
    return GraphTool()


@pytest.fixture
def _patch_workspace(monkeypatch):
    monkeypatch.setattr("axm_ast.core.workspace.detect_workspace", lambda _: None)


# --- Unit tests ---


@pytest.mark.usefixtures("_patch_workspace")
def test_graph_json_includes_nodes(tool, tmp_path, monkeypatch):
    """JSON format must include a 'nodes' key listing all module names."""
    root = tmp_path / "mypkg"
    root.mkdir()
    pkg = _make_pkg(
        root,
        ["__init__.py", "cli.py", "core.py", "models.py"],
        [("cli", "core")],
    )
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)

    result = tool.execute(path=str(root), format="json")

    assert result.success
    assert "nodes" in result.data
    nodes = set(result.data["nodes"])
    assert nodes == {"mypkg", "cli", "core", "models"}


@pytest.mark.usefixtures("_patch_workspace")
def test_graph_json_includes_edges(tool, tmp_path, monkeypatch):
    """JSON format must include edges (adjacency list) under 'graph' key."""
    root = tmp_path / "mypkg"
    root.mkdir()
    pkg = _make_pkg(
        root,
        ["__init__.py", "cli.py", "core.py", "models.py"],
        [("cli", "core"), ("cli", "models"), ("core", "models")],
    )
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)

    result = tool.execute(path=str(root), format="json")

    assert result.success
    graph = result.data["graph"]
    assert "cli" in graph
    assert "core" in graph["cli"]
    assert "models" in graph["cli"]
    assert "core" in graph
    assert "models" in graph["core"]


# --- Functional tests ---


@pytest.mark.usefixtures("_patch_workspace")
def test_graph_json_vs_mermaid_consistency(tool, tmp_path, monkeypatch):
    """Nodes and edges in JSON must be consistent with mermaid output."""
    root = tmp_path / "mypkg"
    root.mkdir()
    pkg = _make_pkg(
        root,
        ["__init__.py", "cli.py", "core.py"],
        [("cli", "core")],
    )
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)

    json_result = tool.execute(path=str(root), format="json")
    mermaid_result = tool.execute(path=str(root), format="mermaid")

    assert json_result.success
    assert mermaid_result.success

    json_nodes = set(json_result.data["nodes"])

    # Parse mermaid node labels from lines like:  node_name["dotted.name"]
    mermaid_text = mermaid_result.data["mermaid"]
    mermaid_nodes = set()
    for line in mermaid_text.splitlines():
        line = line.strip()
        if '["' in line and '"]' in line:
            label = line.split('["')[1].split('"]')[0]
            mermaid_nodes.add(label)

    assert json_nodes == mermaid_nodes

    # Edges in json must appear in mermaid
    json_graph = json_result.data["graph"]
    for src, targets in json_graph.items():
        for target in targets:
            safe_src = src.replace(".", "_")
            safe_target = target.replace(".", "_")
            assert f"{safe_src} --> {safe_target}" in mermaid_text


# --- Edge cases ---


@pytest.mark.usefixtures("_patch_workspace")
def test_graph_no_internal_imports(tool, tmp_path, monkeypatch):
    """Package with isolated modules: nodes present, graph empty."""
    root = tmp_path / "isolated"
    root.mkdir()
    pkg = _make_pkg(
        root,
        ["__init__.py", "alpha.py", "beta.py"],
        [],
    )
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)

    result = tool.execute(path=str(root), format="json")

    assert result.success
    assert len(result.data["nodes"]) >= 1
    assert result.data["graph"] == {}


@pytest.mark.usefixtures("_patch_workspace")
def test_graph_single_module(tool, tmp_path, monkeypatch):
    """Package with only __init__.py: one node, empty graph."""
    root = tmp_path / "single"
    root.mkdir()
    pkg = _make_pkg(root, ["__init__.py"], [])
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)

    result = tool.execute(path=str(root), format="json")

    assert result.success
    assert len(result.data["nodes"]) >= 1
    assert "single" in result.data["nodes"]
    assert result.data["graph"] == {}
