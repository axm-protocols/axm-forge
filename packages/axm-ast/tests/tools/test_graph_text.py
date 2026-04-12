from __future__ import annotations

from pathlib import Path

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


# ── Functional-test fixtures ────────────────────────────────────────


@pytest.fixture
def fixture_pkg(tmp_path):
    """Minimal Python package for integration tests."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    src = pkg / "src" / "mypkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "cli.py").write_text("from mypkg.core import parser\n")
    core = src / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "parser.py").write_text("from mypkg import utils\n")
    (core / "cache.py").write_text("")
    (src / "utils.py").write_text("")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n\n'
        '[build-system]\nrequires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )
    return pkg


@pytest.fixture
def fixture_ws(tmp_path):
    """Minimal uv workspace for integration tests."""
    ws = tmp_path / "myws"
    ws.mkdir()
    (ws / "pyproject.toml").write_text(
        '[project]\nname = "myws"\nversion = "0.1.0"\n\n'
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    pkgs = ws / "packages"
    pkgs.mkdir()
    for name, deps in [("pkg-a", ["pkg-b"]), ("pkg-b", []), ("pkg-c", ["pkg-a"])]:
        p = pkgs / name
        src = p / "src" / name.replace("-", "_")
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        dep_str = ", ".join(f'"{d}"' for d in deps)
        (p / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            f"dependencies = [{dep_str}]\n\n"
            '[build-system]\nrequires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
        )
    return ws


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
# Functional tests — execute returns text + unchanged data
# ══════════════════════════════════════════════════════════════════════


class TestExecutePkgWithText:
    def test_execute_pkg_json_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="json")
        assert result.success
        assert isinstance(result.text, str)
        assert "ast_graph" in result.text
        assert "nodes" in result.data
        assert isinstance(result.data["nodes"], list)

    def test_execute_pkg_mermaid_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="mermaid")
        assert result.success
        assert isinstance(result.text, str)
        assert "mermaid" in result.data

    def test_execute_pkg_text_has_text(self, fixture_pkg: Path) -> None:
        result = GraphTool().execute(path=str(fixture_pkg), format="text")
        assert result.success
        assert isinstance(result.text, str)
        assert "text" in result.data


class TestExecuteWsWithText:
    def test_execute_ws_json_has_text(self, fixture_ws: Path) -> None:
        result = GraphTool().execute(path=str(fixture_ws), format="json")
        assert result.success
        assert isinstance(result.text, str)
        assert "graph" in result.data

    def test_execute_ws_mermaid_has_text(self, fixture_ws: Path) -> None:
        result = GraphTool().execute(path=str(fixture_ws), format="mermaid")
        assert result.success
        assert isinstance(result.text, str)
        assert "mermaid" in result.data


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
