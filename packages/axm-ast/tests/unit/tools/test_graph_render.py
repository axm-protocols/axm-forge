from __future__ import annotations

import pytest

from axm_ast.tools.graph import GraphTool


@pytest.fixture
def render():
    """Shortcut to the staticmethod under test."""
    return GraphTool._render_pkg_text


# ── Unit tests ──────────────────────────────────────────────────────────


def test_render_pkg_text_basic(render):
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


def test_render_pkg_text_grouped(render):
    """Modules with dotted names grouped under prefix."""
    nodes = ["core.parser", "core.cache", "utils"]
    graph: dict[str, list[str]] = {}

    result = render("my_pkg", nodes, graph, mermaid_str=None)

    assert "Modules:" in result
    # standalone
    assert "  utils" in result
    # grouped
    assert "  core: parser cache" in result


def test_render_pkg_text_mermaid(render):
    """Graph with edges + mermaid string -> Mermaid block appended."""
    nodes = ["a", "b"]
    graph = {"a": ["b"]}
    mermaid = "graph LR\n  a --> b"

    result = render("pkg", nodes, graph, mermaid_str=mermaid)

    assert "```mermaid" in result
    assert mermaid in result
    assert result.endswith("```")


def test_render_pkg_text_no_edges(render):
    """Modules only, empty graph -> No Edges section, no mermaid."""
    nodes = ["alpha", "beta"]
    graph: dict[str, list[str]] = {}

    result = render("pkg", nodes, graph, mermaid_str=None)

    assert "0 edges" in result
    assert "Edges:" not in result
    assert "mermaid" not in result


# ── Edge cases ──────────────────────────────────────────────────────────


def test_render_pkg_text_single_module(render):
    """1 node, 0 edges -> singular 'module' label."""
    nodes = ["only"]
    graph: dict[str, list[str]] = {}

    result = render("pkg", nodes, graph, mermaid_str=None)

    assert "1 module · 0 edges" in result


def test_render_pkg_text_empty_graph_with_mermaid(render):
    """mermaid_str provided but graph={} -> Mermaid block suppressed."""
    nodes = ["a"]
    graph: dict[str, list[str]] = {}
    mermaid = "graph LR\n  a"

    result = render("pkg", nodes, graph, mermaid_str=mermaid)

    assert "mermaid" not in result
