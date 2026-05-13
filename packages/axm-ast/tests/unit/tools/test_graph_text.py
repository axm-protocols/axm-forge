from __future__ import annotations

import pytest

from axm_ast.tools.graph import GraphTool

# ── Unit-test fixtures ──────────────────────────────────────────────


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


# ══════════════════════════════════════════════════════════════════════
# Unit tests — _render_pkg_text
# ══════════════════════════════════════════════════════════════════════


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
        assert "\u2192" in text  # →

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


# ══════════════════════════════════════════════════════════════════════
# Unit tests — _render_ws_text
# ══════════════════════════════════════════════════════════════════════


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
        assert "\u2192" in text  # →
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


# ══════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════


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
