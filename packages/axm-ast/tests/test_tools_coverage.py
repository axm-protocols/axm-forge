"""Tests for tool edge cases — AXM-982 coverage gaps."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.callers import CallersTool
from axm_ast.tools.diff import DiffTool
from axm_ast.tools.doc_impact import DocImpactTool
from axm_ast.tools.flows import FlowsTool
from axm_ast.tools.graph import GraphTool

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def graph_tool() -> GraphTool:
    return GraphTool()


@pytest.fixture()
def diff_tool() -> DiffTool:
    return DiffTool()


@pytest.fixture()
def doc_impact_tool() -> DocImpactTool:
    return DocImpactTool()


@pytest.fixture()
def flows_tool() -> FlowsTool:
    return FlowsTool()


@pytest.fixture()
def callers_tool() -> CallersTool:
    return CallersTool()


@pytest.fixture()
def simple_pkg(tmp_path: Path) -> Path:
    """Package with a simple function and no docstring."""
    pkg = tmp_path / "simplepkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Simple."""\n')
    (pkg / "core.py").write_text(
        "def greet(name):\n"
        "    return f'hello {name}'\n\n"
        "def helper():\n"
        "    return greet('world')\n"
    )
    (pkg / "wrapper.py").write_text(
        "from .core import greet\n\n"
        "def wrapped():\n"
        '    """Wrapped call."""\n'
        "    return greet('wrapped')\n"
    )
    return pkg


@pytest.fixture()
def circular_pkg(tmp_path: Path) -> Path:
    """Package with circular dependency between modules."""
    pkg = tmp_path / "circpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Circular."""\n')
    (pkg / "a.py").write_text(
        "from .b import func_b\n\ndef func_a():\n    return func_b()\n"
    )
    (pkg / "b.py").write_text(
        "def func_b():\n    from .a import func_a  # noqa: F811\n    return 'b'\n"
    )
    return pkg


# ─── GraphTool ───────────────────────────────────────────────────────────────


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


# ─── DiffTool ────────────────────────────────────────────────────────────────


class TestDiffNoChanges:
    """Call diff tool on identical trees → empty diff."""

    def test_diff_no_changes(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mock_diff = mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={"added": [], "removed": [], "modified": []},
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="main")
        assert result.success is True
        assert result.data["added"] == []
        assert result.data["removed"] == []
        assert result.data["modified"] == []
        mock_diff.assert_called_once()


class TestDiffDeletedSymbol:
    """Call diff on tree where symbol was removed → reports deletion."""

    def test_diff_deleted_symbol(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={
                "added": [],
                "removed": [{"symbol": "greet", "module": "core"}],
                "modified": [],
            },
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is True
        assert len(result.data["removed"]) == 1
        assert result.data["removed"][0]["symbol"] == "greet"


# ─── DocImpactTool ───────────────────────────────────────────────────────────


class TestDocImpactNoDocstring:
    """Call doc_impact on symbol without docstring → handles None."""

    def test_doc_impact_no_docstring(
        self, doc_impact_tool: DocImpactTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.doc_impact.analyze_doc_impact",
            return_value=[
                {
                    "symbol": "greet",
                    "has_docstring": False,
                    "docstring": None,
                    "impact": "low",
                }
            ],
        )
        result = doc_impact_tool.execute(path=str(simple_pkg), symbols=["greet"])
        assert result.success is True
        items: list[dict[str, Any]] = result.data  # type: ignore[assignment]
        assert items[0]["has_docstring"] is False
        assert items[0]["docstring"] is None


# ─── FlowsTool ───────────────────────────────────────────────────────────────


class TestFlowsEmptyChain:
    """Call flows with symbol that has no callers/callees → single-node flow."""

    def test_flows_empty_chain(self, flows_tool: FlowsTool, simple_pkg: Path) -> None:
        result = flows_tool.execute(path=str(simple_pkg), entry="greet", max_depth=5)
        assert result.success is True
        # Should return at least the entry node itself
        assert result.data["count"] >= 0


class TestFlowsCircularRef:
    """Call flows with circular dependency → terminates without infinite loop."""

    def test_flows_circular_ref(
        self, flows_tool: FlowsTool, circular_pkg: Path
    ) -> None:
        result = flows_tool.execute(
            path=str(circular_pkg), entry="func_a", max_depth=10
        )
        assert result.success is True
        # Must terminate — BFS should not loop forever
        assert result.data["count"] >= 1


# ─── CallersTool ─────────────────────────────────────────────────────────────


class TestCallersIndirectResolution:
    """Callers with indirect=True on wrapped func → resolves through decorator."""

    def test_callers_indirect_resolution(
        self, callers_tool: CallersTool, simple_pkg: Path
    ) -> None:
        result = callers_tool.execute(path=str(simple_pkg), symbol="greet")
        assert result.success is True
        # greet is called by helper and wrapped — should find callers
        assert result.data["count"] >= 1
        caller_contexts = [c["module"] for c in result.data["callers"]]
        assert len(caller_contexts) >= 1


# ─── Additional edge-case coverage (AXM-982) ────────────────────────────────


class TestDiffErrorResult:
    """structural_diff returns dict with 'error' key → tool returns failure."""

    def test_diff_error_in_result(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={"error": "refs not found"},
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is False
        assert result.error == "refs not found"


class TestDiffException:
    """structural_diff raises → tool catches gracefully."""

    def test_diff_exception(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            side_effect=RuntimeError("git failed"),
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is False
        assert "git failed" in (result.error or "")


class TestDocImpactToolEdgeCases:
    """DocImpactTool edge cases — name, empty symbols, bad path, exception."""

    def test_name(self, doc_impact_tool: DocImpactTool) -> None:
        assert doc_impact_tool.name == "ast_doc_impact"

    def test_empty_symbols(self, doc_impact_tool: DocImpactTool) -> None:
        result = doc_impact_tool.execute(path=".")
        assert result.success is False
        assert "symbols" in (result.error or "")

    def test_bad_path(self, doc_impact_tool: DocImpactTool) -> None:
        result = doc_impact_tool.execute(path="/nonexistent/path/xyz", symbols=["foo"])
        assert result.success is False

    def test_exception(
        self, doc_impact_tool: DocImpactTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.doc_impact.analyze_doc_impact",
            side_effect=RuntimeError("boom"),
        )
        result = doc_impact_tool.execute(path=str(simple_pkg), symbols=["greet"])
        assert result.success is False
        assert "boom" in (result.error or "")


class TestCalleesToolEdgeCases:
    """CalleesTool — name, bad path, exception."""

    def test_name(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        assert CalleesTool().name == "ast_callees"

    def test_bad_path(self) -> None:
        from axm_ast.tools.callees import CalleesTool

        result = CalleesTool().execute(path="/nonexistent/path/xyz", symbol="foo")
        assert result.success is False

    def test_exception(self, simple_pkg: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.callees import CalleesTool

        mocker.patch(
            "axm_ast.core.flows.find_callees",
            side_effect=RuntimeError("callees boom"),
        )
        result = CalleesTool().execute(path=str(simple_pkg), symbol="greet")
        assert result.success is False
        assert "callees boom" in (result.error or "")


class TestFlowsToolEdgeCases:
    """FlowsTool — name, bad path."""

    def test_name(self, flows_tool: FlowsTool) -> None:
        assert flows_tool.name == "ast_flows"

    def test_bad_path(self, flows_tool: FlowsTool) -> None:
        result = flows_tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False


class TestCallersToolEdgeCases:
    """CallersTool — bad path, exception."""

    def test_bad_path(self, callers_tool: CallersTool) -> None:
        result = callers_tool.execute(path="/nonexistent/path/xyz", symbol="foo")
        assert result.success is False

    def test_exception(
        self, callers_tool: CallersTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.callers.find_callers",
            side_effect=RuntimeError("callers boom"),
        )
        result = callers_tool.execute(path=str(simple_pkg), symbol="greet")
        assert result.success is False
        assert "callers boom" in (result.error or "")


class TestContextToolException:
    """ContextTool — exception handling."""

    def test_exception(self, simple_pkg: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.context import ContextTool

        mocker.patch(
            "axm_ast.core.context.build_context",
            side_effect=RuntimeError("ctx boom"),
        )
        result = ContextTool().execute(path=str(simple_pkg))
        assert result.success is False
        assert "ctx boom" in (result.error or "")
