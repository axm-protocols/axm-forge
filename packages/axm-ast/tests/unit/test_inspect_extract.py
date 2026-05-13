"""Tests for extracted InspectTool helpers — TDD for AXM-954 refactoring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from axm.tools.base import ToolResult

from axm_ast.tools.inspect import InspectTool


@pytest.fixture
def tool():
    return InspectTool()


@pytest.fixture
def mock_pkg():
    """Minimal PackageInfo with modules for resolution tests."""
    pkg = MagicMock()

    mod_alpha = MagicMock()
    mod_alpha.path = "/fake/src/pkg/alpha.py"
    mod_alpha.docstring = "Alpha"
    mod_alpha.functions = [MagicMock(name="fn_a")]
    mod_alpha.classes = []

    mod_beta = MagicMock()
    mod_beta.path = "/fake/src/pkg/beta.py"
    mod_beta.docstring = "Beta"
    mod_beta.functions = []
    mod_beta.classes = [MagicMock(name="Cls")]

    mod_alpha_v2 = MagicMock()
    mod_alpha_v2.path = "/fake/src/pkg/alpha_v2.py"
    mod_alpha_v2.docstring = ""
    mod_alpha_v2.functions = []
    mod_alpha_v2.classes = []

    pkg.modules = [mod_alpha, mod_beta, mod_alpha_v2]
    pkg.module_names = ["pkg.alpha", "pkg.beta", "pkg.alpha_v2"]
    return pkg


class TestInspectBatch:
    """InspectTool._inspect_batch — extracted batch loop."""

    def test_collects_successful_symbols(self, tool):
        project_path = MagicMock()
        tool._inspect_symbol = MagicMock(
            return_value=ToolResult(
                success=True,
                data={"symbol": {"name": "Foo", "kind": "class"}},
            )
        )
        result = tool._inspect_batch(project_path, ["Foo"], source=False)
        assert result.success
        assert len(result.data["symbols"]) == 1
        assert result.data["symbols"][0]["name"] == "Foo"

    def test_includes_error_entry_for_failed_lookup(self, tool):
        project_path = MagicMock()
        tool._inspect_symbol = MagicMock(
            return_value=ToolResult(success=False, error="Symbol not found")
        )
        result = tool._inspect_batch(project_path, ["Missing"], source=False)
        assert result.success
        assert result.data["symbols"][0]["name"] == "Missing"
        assert result.data["symbols"][0]["error"] == "Symbol not found"

    def test_multiple_symbols_mixed_results(self, tool):
        project_path = MagicMock()
        ok = ToolResult(success=True, data={"symbol": {"name": "A", "kind": "class"}})
        err = ToolResult(success=False, error="not found")
        tool._inspect_symbol = MagicMock(side_effect=[ok, err])
        result = tool._inspect_batch(project_path, ["A", "B"], source=False)
        assert result.success
        assert len(result.data["symbols"]) == 2
        assert result.data["symbols"][0]["name"] == "A"
        assert result.data["symbols"][1]["error"] == "not found"

    def test_non_list_returns_error(self, tool):
        result = tool._inspect_batch(MagicMock(), "not-a-list", source=False)
        assert not result.success
        assert result.error is not None
        assert "must be a list" in result.error


class TestResolveModule:
    """InspectTool._resolve_module — module name matching."""

    def test_exact_match_returns_module(self, tool, mock_pkg):
        result = tool._resolve_module(mock_pkg, "pkg.alpha")
        assert result is not None
        assert not isinstance(result, ToolResult)

    def test_substring_unique_returns_module(self, tool, mock_pkg):
        result = tool._resolve_module(mock_pkg, "beta")
        assert result is not None
        assert not isinstance(result, ToolResult)

    def test_substring_ambiguous_returns_error(self, tool, mock_pkg):
        result = tool._resolve_module(mock_pkg, "alpha")
        assert isinstance(result, ToolResult)
        assert not result.success
        assert result.error is not None
        assert "Multiple modules" in result.error

    def test_no_match_returns_none(self, tool, mock_pkg):
        result = tool._resolve_module(mock_pkg, "nonexistent")
        assert result is None
