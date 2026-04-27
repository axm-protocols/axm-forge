"""Tests for axm_ast.core.flows pydantic models (extra=forbid).

Flow logic tests live in ``tests/test_flows.py`` until that file is
relocated in a later pyramid pass.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_ast.core.flows import EntryPoint, FlowStep, format_flows


class TestEntryPointExtraForbid:
    """EntryPoint rejects unknown fields."""

    def test_entry_point_rejects_extra(self) -> None:
        from axm_ast.core.flows import EntryPoint

        with pytest.raises(ValidationError, match="extra_forbidden"):
            EntryPoint(
                name="x",
                module="m",
                kind="test",
                line=1,
                framework="pytest",
                extra_field="bad",  # type: ignore[call-arg]
            )


class TestFlowStepExtraForbid:
    """FlowStep rejects unknown fields."""

    def test_flow_step_rejects_extra(self) -> None:
        from axm_ast.core.flows import FlowStep

        with pytest.raises(ValidationError, match="extra_forbidden"):
            FlowStep(
                name="x",
                module="m",
                line=1,
                depth=0,
                chain=[],
                whoops=True,  # type: ignore[call-arg]
            )


class TestFormatFlows:
    """Test output formatting."""

    def test_format_empty(self) -> None:
        """Empty results → clean message."""
        assert format_flows([]) == "✅ No entry points detected."

    def test_format_results(self) -> None:
        """Results → grouped output."""
        entries = [
            EntryPoint(
                name="index",
                module="routes",
                kind="decorator",
                line=5,
                framework="flask",
            ),
            EntryPoint(
                name="test_foo",
                module="tests",
                kind="test",
                line=1,
                framework="pytest",
            ),
        ]
        output = format_flows(entries)
        assert "2 entry point(s)" in output
        assert "flask" in output
        assert "pytest" in output
        assert "index" in output
        assert "test_foo" in output


class TestFlowStepSourceField:
    """FlowStep model accepts optional source field."""

    def test_flowstep_source_default_none(self) -> None:
        """FlowStep without source → defaults to None."""
        step = FlowStep(name="f", module="m", line=1, depth=0, chain=["f"])
        assert step.source is None

    def test_flowstep_source_explicit(self) -> None:
        """FlowStep with explicit source → stored."""
        step = FlowStep(
            name="f", module="m", line=1, depth=0, chain=["f"], source="def f(): pass"
        )
        assert step.source == "def f(): pass"


class TestParseImportFromNodeBasic:
    """_parse_import_from_node extracts module and imported names."""

    def test_basic_import(self) -> None:
        """``from .response import HttpResponse`` → ('.response', ['HttpResponse'])."""
        from axm_ast.core.flows import _parse_import_from_node
        from axm_ast.core.parser import parse_source

        code = "from .response import HttpResponse\n"
        tree = parse_source(code)
        nodes = [
            n
            for n in getattr(tree.root_node, "children", [])
            if getattr(n, "type", "") == "import_from_statement"
        ]
        assert len(nodes) == 1
        module, names = _parse_import_from_node(nodes[0])
        assert module == ".response"
        assert names == ["HttpResponse"]


class TestParseImportFromNodeMulti:
    """_parse_import_from_node handles multi-name imports."""

    def test_multi_import(self) -> None:
        """``from .models import A, B`` → ('.models', ['A', 'B'])."""
        from axm_ast.core.flows import _parse_import_from_node
        from axm_ast.core.parser import parse_source

        code = "from .models import A, B\n"
        tree = parse_source(code)
        nodes = [
            n
            for n in getattr(tree.root_node, "children", [])
            if getattr(n, "type", "") == "import_from_statement"
        ]
        assert len(nodes) == 1
        module, names = _parse_import_from_node(nodes[0])
        assert module == ".models"
        assert set(names) == {"A", "B"}


class TestResolveRelativeModule:
    """_resolve_relative_module resolves dotted paths."""

    def test_single_dot(self) -> None:
        """.response from django.http → django.http.response."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module(".response", "django.http")
        assert result == "django.http.response"

    def test_double_dot(self) -> None:
        """..utils from django.http.response → django.utils."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module("..utils", "django.http.response")
        assert result == "django.http.utils"

    def test_dot_only(self) -> None:
        """. from django.http → django.http (no rel_name)."""
        from axm_ast.core.flows import _resolve_relative_module

        result = _resolve_relative_module(".", "django.http")
        assert result == "django.http"
