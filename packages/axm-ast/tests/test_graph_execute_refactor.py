"""Tests for GraphTool.execute refactor — verify behavioral equivalence.

Ensures all output formats (json, mermaid, text) produce identical results
after extracting branches from execute into private methods.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_ast.tools.graph import GraphTool


def _make_pkg(
    root: Path, module_files: list[str], edges: list[tuple[str, str]]
) -> SimpleNamespace:
    """Build a minimal PackageInfo-like namespace for testing."""
    mods = [SimpleNamespace(path=root / f) for f in module_files]
    return SimpleNamespace(root=root, modules=mods, dependency_edges=edges)


@pytest.fixture()
def tool() -> GraphTool:
    return GraphTool()


@pytest.fixture()
def _patch_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("axm_ast.core.workspace.detect_workspace", lambda _: None)


@pytest.fixture()
def pkg_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Package with edges for text/mermaid/json output tests."""
    root = tmp_path / "demopkg"
    root.mkdir()
    pkg = _make_pkg(
        root,
        ["__init__.py", "cli.py", "core.py", "utils.py"],
        [("cli", "core"), ("core", "utils")],
    )
    monkeypatch.setattr("axm_ast.core.workspace.detect_workspace", lambda _: None)
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _: pkg)
    return root


# ─── Unit: text format output ───────────────────────────────────────────────


class TestGraphTextFormat:
    """Text format must list nodes and edges in a readable layout."""

    def test_text_returns_text_key(self, tool: GraphTool, pkg_root: Path) -> None:
        result = tool.execute(path=str(pkg_root), format="text")
        assert result.success is True
        assert "text" in result.data
        assert isinstance(result.data["text"], str)

    def test_text_contains_nodes_section(self, tool: GraphTool, pkg_root: Path) -> None:
        result = tool.execute(path=str(pkg_root), format="text")
        text = result.data["text"]
        assert "Nodes:" in text
        assert "demopkg" in text
        assert "cli" in text
        assert "core" in text
        assert "utils" in text

    def test_text_contains_edges_section(self, tool: GraphTool, pkg_root: Path) -> None:
        result = tool.execute(path=str(pkg_root), format="text")
        text = result.data["text"]
        assert "Edges:" in text
        assert "cli -> core" in text
        assert "core -> utils" in text

    def test_text_also_includes_graph_and_nodes(
        self, tool: GraphTool, pkg_root: Path
    ) -> None:
        """Text format keeps graph + nodes keys alongside text."""
        result = tool.execute(path=str(pkg_root), format="text")
        assert "graph" in result.data
        assert "nodes" in result.data


# ─── Unit: existing formats unchanged ───────────────────────────────────────


class TestGraphExistingFormats:
    """JSON and mermaid output must remain unchanged after refactor."""

    def test_json_has_graph_and_nodes(self, tool: GraphTool, pkg_root: Path) -> None:
        result = tool.execute(path=str(pkg_root), format="json")
        assert result.success is True
        assert "graph" in result.data
        assert "nodes" in result.data
        assert "mermaid" not in result.data
        assert "text" not in result.data

    def test_mermaid_has_mermaid_key(self, tool: GraphTool, pkg_root: Path) -> None:
        result = tool.execute(path=str(pkg_root), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert isinstance(result.data["mermaid"], str)


# ─── Functional: workspace path ─────────────────────────────────────────────


class TestGraphWorkspacePath:
    """Workspace detection branch returns workspace graph."""

    def test_workspace_json(
        self, tool: GraphTool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_info = SimpleNamespace(packages=[])
        ws_graph: dict[str, Any] = {"pkg_a": ["pkg_b"]}
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.analyze_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            lambda _: ws_graph,
        )
        result = tool.execute(path=str(tmp_path), format="json")
        assert result.success is True
        assert result.data["graph"] == {"pkg_a": ["pkg_b"]}
        assert "mermaid" not in result.data

    def test_workspace_mermaid(
        self, tool: GraphTool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_info = SimpleNamespace(packages=[])
        ws_graph: dict[str, Any] = {"pkg_a": ["pkg_b"]}
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.analyze_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            lambda _: ws_graph,
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.format_workspace_graph_mermaid",
            lambda _: "graph TD\n  pkg_a --> pkg_b",
        )
        result = tool.execute(path=str(tmp_path), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert "graph" in result.data
        assert result.data["graph"] == {"pkg_a": ["pkg_b"]}


# ─── Edge cases ─────────────────────────────────────────────────────────────


class TestGraphEdgeCasesRefactor:
    """Edge cases from test_spec."""

    def test_invalid_path(self, tool: GraphTool) -> None:
        """Non-existent directory returns ToolResult(success=False)."""
        result = tool.execute(path="/nonexistent/surely/missing")
        assert result.success is False
        assert result.error

    def test_unknown_format_falls_through_to_json(
        self, tool: GraphTool, pkg_root: Path
    ) -> None:
        """Unknown format (e.g. 'xml') produces JSON-like output.

        Verify no mermaid/text keys are present.
        """
        result = tool.execute(path=str(pkg_root), format="xml")
        assert result.success is True
        assert "graph" in result.data
        assert "nodes" in result.data
        assert "mermaid" not in result.data
        assert "text" not in result.data

    def test_workspace_path_detected(
        self, tool: GraphTool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When workspace is detected, workspace graph is returned."""
        ws_info = SimpleNamespace(packages=[])
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.analyze_workspace", lambda _: ws_info
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            lambda _: {},
        )
        result = tool.execute(path=str(tmp_path))
        assert result.success is True
        assert result.data["graph"] == {}
