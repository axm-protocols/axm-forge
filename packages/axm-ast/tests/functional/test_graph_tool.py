"""Functional tests for GraphTool — public MCP tool API."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.graph import GraphTool

AXM_AST_PATH = str(
    Path(__file__).resolve().parents[2]  # tests/functional/.. -> axm-ast root
)


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
