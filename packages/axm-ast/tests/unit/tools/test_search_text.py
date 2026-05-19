from __future__ import annotations

import re
from typing import Any

from axm_ast.models.nodes import SymbolKind
from axm_ast.tools.search_text import format_symbol_line, format_text_header

# ── Helpers ──────────────────────────────────────────────────────────────────


def _func_dict(
    name: str,
    sig: str,
    ret: str | None = None,
    kind: str = "function",
) -> dict[str, Any]:
    d: dict[str, Any] = {"name": name, "module": "mod", "signature": sig, "kind": kind}
    if ret is not None:
        d["return_type"] = ret
    return d


def _class_dict(name: str) -> dict[str, Any]:
    return {"name": name, "module": "mod", "kind": "class"}


def _var_dict(
    name: str,
    annotation: str | None = None,
    value_repr: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"name": name, "module": "mod", "kind": "variable"}
    if annotation is not None:
        d["annotation"] = annotation
    if value_repr is not None:
        d["value_repr"] = value_repr
    return d


# ── Unit: _format_text_header ──────────────────────────────────────────────────


class TestFormatTextHeader:
    def test_text_header_name_filter(self):
        h = format_text_header(
            search_filters={
                "name": "foo",
                "returns": None,
                "kind": None,
                "inherits": None,
            },
            count=5,
        )
        assert re.search(r"name~.foo.", h)
        assert "5 hits" in h
        assert "ast_search" in h

    def test_text_header_combined_filters(self):
        h = format_text_header(
            search_filters={
                "name": "x",
                "returns": None,
                "kind": SymbolKind.CLASS,
                "inherits": None,
            },
            count=3,
        )
        assert re.search(r"name~.x.", h)
        assert "kind=class" in h
        assert "3 hits" in h

    def test_text_header_no_filters(self):
        h = format_text_header(
            search_filters={
                "name": None,
                "returns": None,
                "kind": None,
                "inherits": None,
            },
            count=10,
        )
        assert "ast_search" in h
        assert "10 hits" in h

    def test_text_header_zero_results(self):
        h = format_text_header(
            search_filters={
                "name": "z",
                "returns": None,
                "kind": None,
                "inherits": None,
            },
            count=0,
        )
        assert "0 hits" in h
        assert "ast_search" in h


# ── Unit: _format_symbol_line ──────────────────────────────────────────────────


class TestFormatSymbolLine:
    def test_format_function_line(self):
        sym = _func_dict("foo", "def foo(a: int, b: str) -> bool", ret="bool")
        line = format_symbol_line(sym)
        assert "foo" in line
        assert "bool" in line

    def test_format_class_line(self):
        sym = _class_dict("MyClass")
        line = format_symbol_line(sym)
        assert "MyClass" in line

    def test_format_variable_line_annotated(self):
        sym = _var_dict("x", annotation="int", value_repr="42")
        line = format_symbol_line(sym)
        assert "x" in line
        assert "int" in line
        assert "42" in line

    def test_format_variable_line_no_annotation(self):
        sym = _var_dict("y", value_repr="[]")
        line = format_symbol_line(sym)
        assert "y" in line
        assert "[]" in line


# ── Edge cases ─────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_return_type(self):
        sym = _func_dict("do_stuff", "def do_stuff(x: int)")
        line = format_symbol_line(sym)
        assert line == "do_stuff(x: int)"
        assert "->" not in line

    def test_very_long_signature(self):
        params = ", ".join(f"p{i}: str" for i in range(12))
        sig = f"def big({params}) -> None"
        sym = _func_dict("big", sig, ret="None")
        line = format_symbol_line(sym)
        assert line.startswith("big(")
        assert "-> None" in line
        assert "\n" not in line

    def test_variable_no_annotation_no_value(self):
        sym = _var_dict("x")
        line = format_symbol_line(sym)
        assert line == "x"

    def test_inherits_filter_in_header(self):
        h = format_text_header(
            search_filters={
                "name": None,
                "returns": None,
                "kind": None,
                "inherits": "AXMTool",
            },
            count=2,
        )
        assert "inherits=AXMTool" in h
        assert "2 hits" in h
