"""Unit tests for GraphTool.execute refactor."""

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


@pytest.fixture()
def tool() -> GraphTool:
    return GraphTool()


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
