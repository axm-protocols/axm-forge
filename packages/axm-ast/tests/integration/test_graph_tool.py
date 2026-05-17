from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.graph import GraphTool
from tests.integration._helpers import _assert_tool_result
from tests.unit._helpers import _EDGE_RE, _NODE_DECL_RE


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


@pytest.fixture()
def tool() -> GraphTool:
    """Provide a fresh GraphTool instance."""
    return GraphTool()


class TestGraphJSON:
    """Tests for default JSON format output."""

    def test_returns_graph_dict(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg))
        assert result.success is True
        assert "graph" in result.data
        assert isinstance(result.data["graph"], dict)

    def test_graph_has_edges(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg))
        graph = result.data["graph"]
        # core imports utils, __init__ imports core
        all_targets = []
        for targets in graph.values():
            all_targets.extend(targets)
        assert len(all_targets) >= 1


class TestGraphMermaid:
    """Tests for mermaid format output."""

    def test_mermaid_returns_string(self, tool: GraphTool, graph_pkg: Path) -> None:
        result = tool.execute(path=str(graph_pkg), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert isinstance(result.data["mermaid"], str)

    def test_mermaid_contains_graph_keyword(
        self, tool: GraphTool, graph_pkg: Path
    ) -> None:
        result = tool.execute(path=str(graph_pkg), format="mermaid")
        mermaid_lower = result.data["mermaid"].lower()
        assert "graph" in mermaid_lower or "flowchart" in mermaid_lower


class TestGraphEdgeCasesIntegration:
    """Edge cases for GraphTool (with real filesystem I/O)."""

    def test_empty_package(self, tool: GraphTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert isinstance(result.data["graph"], dict)

    def test_no_internal_imports(self, tool: GraphTool, tmp_path: Path) -> None:
        """Package with no internal imports → empty graph."""
        pkg = tmp_path / "noimports"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""No imports."""\n')
        (pkg / "a.py").write_text("x = 1\n")
        (pkg / "b.py").write_text("y = 2\n")
        result = tool.execute(path=str(pkg))
        assert result.success is True
        graph = result.data["graph"]
        total_edges = sum(len(v) for v in graph.values())
        assert total_edges == 0


@pytest.fixture()
def graph_pkg(tmp_path: Path) -> Path:
    """Create a package with internal imports for graph tests."""
    pkg = tmp_path / "graphdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Graph demo."""\n\nfrom .core import main\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\nfrom .utils import helper\n\n\n'
        "def main() -> str:\n"
        '    """Entry point."""\n'
        "    return helper()\n"
    )
    (pkg / "utils.py").write_text(
        '"""Utils module."""\n\n\n'
        "def helper() -> str:\n"
        '    """Help."""\n'
        '    return "ok"\n'
    )
    return pkg


def _make_pkg(
    root: Path, module_files: list[str], edges: list[tuple[str, str]]
) -> SimpleNamespace:
    """Build a minimal PackageInfo-like namespace for testing."""
    mods = [SimpleNamespace(path=root / f) for f in module_files]
    return SimpleNamespace(root=root, modules=mods, dependency_edges=edges)


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


@pytest.fixture()
def tool__from_graph_execute_refactor() -> GraphTool:
    return GraphTool()


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


def _make_pkg__from_graph_tool(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


@pytest.fixture()
def tool__from_tools_graph_execute_refactor() -> GraphTool:
    return GraphTool()


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


class TestGraphTextFormat:
    """Text format must list nodes and edges in a readable layout."""

    def test_text_returns_text_key(
        self, tool__from_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        result = tool__from_graph_execute_refactor.execute(
            path=str(pkg_root), format="text"
        )
        assert result.success is True
        assert "text" in result.data
        assert isinstance(result.data["text"], str)

    def test_text_contains_nodes_section(
        self, tool__from_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        result = tool__from_graph_execute_refactor.execute(
            path=str(pkg_root), format="text"
        )
        text = result.data["text"]
        assert "Nodes:" in text
        assert "demopkg" in text
        assert "cli" in text
        assert "core" in text
        assert "utils" in text

    def test_text_contains_edges_section(
        self, tool__from_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        result = tool__from_graph_execute_refactor.execute(
            path=str(pkg_root), format="text"
        )
        text = result.data["text"]
        assert "Edges:" in text
        assert "cli -> core" in text
        assert "core -> utils" in text

    def test_text_also_includes_graph_and_nodes(
        self, tool__from_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        """Text format keeps graph + nodes keys alongside text."""
        result = tool__from_graph_execute_refactor.execute(
            path=str(pkg_root), format="text"
        )
        assert "graph" in result.data
        assert "nodes" in result.data


class TestGraphWorkspacePath:
    """Workspace detection branch returns workspace graph."""

    def test_workspace_json(
        self,
        tool__from_graph_execute_refactor: GraphTool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
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
        result = tool__from_graph_execute_refactor.execute(
            path=str(tmp_path), format="json"
        )
        assert result.success is True
        assert result.data["graph"] == {"pkg_a": ["pkg_b"]}
        assert "mermaid" not in result.data

    def test_workspace_mermaid(
        self,
        tool__from_graph_execute_refactor: GraphTool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
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
        result = tool__from_graph_execute_refactor.execute(
            path=str(tmp_path), format="mermaid"
        )
        assert result.success is True
        assert "mermaid" in result.data
        assert "graph" in result.data
        assert result.data["graph"] == {"pkg_a": ["pkg_b"]}


class TestGraphEdgeCasesRefactorInteg:
    """Edge cases from test_spec (integration, with I/O or fixtures)."""

    def test_unknown_format_falls_through_to_json(
        self, tool__from_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        """Unknown format (e.g. 'xml') produces JSON-like output.

        Verify no mermaid/text keys are present.
        """
        result = tool__from_graph_execute_refactor.execute(
            path=str(pkg_root), format="xml"
        )
        assert result.success is True
        assert "graph" in result.data
        assert "nodes" in result.data
        assert "mermaid" not in result.data
        assert "text" not in result.data

    def test_workspace_path_detected(
        self,
        tool__from_graph_execute_refactor: GraphTool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
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
        result = tool__from_graph_execute_refactor.execute(path=str(tmp_path))
        assert result.success is True
        assert result.data["graph"] == {}


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


def test_graph_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:

    pkg = _make_pkg__from_graph_tool(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.workspace.detect_workspace",
        side_effect=RuntimeError("graph boom"),
    )
    result = GraphTool().execute(path=str(pkg))
    assert result.success is False
    assert "graph boom" in (result.error or "")


class TestGraphToolWorkspace:
    """Cover tools/graph.py workspace branch (lines 52-72)."""

    def test_workspace_json(self, tmp_path: Path, mocker: MagicMock) -> None:

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            return_value={"pkgA": ["pkgB"]},
        )
        pkg = _make_pkg__from_graph_tool(tmp_path, {"__init__.py": ""})
        result = GraphTool().execute(path=str(pkg))
        assert result.success is True
        assert result.data["graph"] == {"pkgA": ["pkgB"]}

    def test_workspace_mermaid(self, tmp_path: Path, mocker: MagicMock) -> None:

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_dep_graph",
            return_value={"pkgA": ["pkgB"]},
        )
        mocker.patch(
            "axm_ast.core.workspace.format_workspace_graph_mermaid",
            return_value="graph LR\n  pkgA --> pkgB",
        )
        pkg = _make_pkg__from_graph_tool(tmp_path, {"__init__.py": ""})
        result = GraphTool().execute(path=str(pkg), format="mermaid")
        assert result.success is True
        assert "mermaid" in result.data
        assert "graph" in result.data


class TestGraphToolIntegration:
    """Tests for ast_graph tool."""

    def test_graph_returns_edges(self, sample_project: Path) -> None:

        tool = GraphTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True
        assert "graph" in result.data

    def test_graph_mermaid_format(self, sample_project: Path) -> None:

        tool = GraphTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), format="mermaid"
        )
        assert result.success is True
        assert "mermaid" in result.data


class TestGraphEmptyInput:
    """Call graph tool with empty symbol list → empty graph, no crash."""

    def test_graph_empty_input(self, graph_tool: GraphTool, tmp_path: Path) -> None:
        pkg = tmp_path / "emptygraph"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Empty."""\n')
        result = graph_tool.execute(path=str(pkg))
        assert result.success is True
        graph = result.data["graph"]
        total_edges = sum(len(v) for v in graph.values())
        assert total_edges == 0


class TestGraphMissingSymbol:
    """Call graph tool with nonexistent symbol → graceful error or empty result."""

    def test_graph_missing_symbol(self, graph_tool: GraphTool, tmp_path: Path) -> None:
        result = graph_tool.execute(path=str(tmp_path / "nonexistent_dir_xyz"))
        assert result.success is False


class TestGraphExistingFormats:
    """JSON and mermaid output must remain unchanged after refactor."""

    def test_json_has_graph_and_nodes(
        self, tool__from_tools_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        result = tool__from_tools_graph_execute_refactor.execute(
            path=str(pkg_root), format="json"
        )
        assert result.success is True
        assert "graph" in result.data
        assert "nodes" in result.data
        assert "mermaid" not in result.data
        assert "text" not in result.data

    def test_mermaid_has_mermaid_key(
        self, tool__from_tools_graph_execute_refactor: GraphTool, pkg_root: Path
    ) -> None:
        result = tool__from_tools_graph_execute_refactor.execute(
            path=str(pkg_root), format="mermaid"
        )
        assert result.success is True
        assert "mermaid" in result.data
        assert isinstance(result.data["mermaid"], str)
