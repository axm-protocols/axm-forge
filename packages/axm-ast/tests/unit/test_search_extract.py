"""Tests for extracted SearchTool helpers — TDD for AXM-954 refactoring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from axm.tools.base import ToolResult

from axm_ast.tools.search import SearchTool


@pytest.fixture
def tool():
    return SearchTool()


class TestValidateKind:
    """SearchTool._validate_kind — kind string → SymbolKind | ToolResult | None."""

    def test_valid_kind_returns_enum(self, tool):
        from axm_ast.models import SymbolKind

        result = tool._validate_kind("function")
        assert result == SymbolKind("function")

    def test_each_valid_kind_accepted(self, tool):
        from axm_ast.models import SymbolKind

        for kind in SymbolKind:
            assert tool._validate_kind(kind.value) == kind

    def test_invalid_kind_returns_error_result(self, tool):
        result = tool._validate_kind("nonexistent")
        assert isinstance(result, ToolResult)
        assert not result.success
        assert result.error is not None
        assert "Invalid kind" in result.error

    def test_none_returns_none(self, tool):
        assert tool._validate_kind(None) is None


class TestFormatSymbol:
    """SearchTool._format_symbol — AST symbol → serialized dict."""

    def test_always_includes_name_and_module(self, tool):
        sym = SimpleNamespace(name="foo")
        entry = tool._format_symbol(sym, "pkg.bar")
        assert entry["name"] == "foo"
        assert entry["module"] == "pkg.bar"

    def test_includes_signature_when_present(self, tool):
        sym = SimpleNamespace(name="f", signature="(x: int) -> str")
        entry = tool._format_symbol(sym, "m")
        assert entry["signature"] == "(x: int) -> str"

    def test_omits_signature_when_absent(self, tool):
        sym = SimpleNamespace(name="f")
        entry = tool._format_symbol(sym, "m")
        assert "signature" not in entry

    def test_includes_return_type_when_present(self, tool):
        sym = SimpleNamespace(name="f", return_type="bool")
        entry = tool._format_symbol(sym, "m")
        assert entry["return_type"] == "bool"

    def test_omits_return_type_when_absent(self, tool):
        sym = SimpleNamespace(name="f")
        entry = tool._format_symbol(sym, "m")
        assert "return_type" not in entry

    def test_variable_sets_kind_field(self, tool):
        sym = SimpleNamespace(name="V", value_repr="42")
        entry = tool._format_symbol(sym, "m")
        assert entry["kind"] == "variable"

    def test_variable_info_includes_annotation(self, tool):
        from axm_ast.models.nodes import VariableInfo

        sym = MagicMock(spec=VariableInfo)
        sym.name = "V"
        sym.value_repr = "42"
        sym.annotation = "int"
        entry = tool._format_symbol(sym, "m")
        assert entry["annotation"] == "int"
        assert entry["value_repr"] == "42"

    def test_variable_info_omits_falsy_fields(self, tool):
        from axm_ast.models.nodes import VariableInfo

        sym = MagicMock(spec=VariableInfo)
        sym.name = "V"
        sym.value_repr = ""
        sym.annotation = ""
        entry = tool._format_symbol(sym, "m")
        assert "annotation" not in entry
        assert "value_repr" not in entry
