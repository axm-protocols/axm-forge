from __future__ import annotations

import re
from typing import Any

import pytest

from axm_ast.tools.search import SearchTool

# ── Helpers ────────────────────────────────────────────────────────────────


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


@pytest.fixture()
def patch_search(monkeypatch):
    """Patch search_symbols and _format_symbol so _search returns controlled dicts."""

    def _setup(formatted_dicts: list[dict[str, Any]]) -> None:
        raw = [(d.get("module", "mod"), d) for d in formatted_dicts]
        monkeypatch.setattr(
            "axm_ast.core.analyzer.search_symbols",
            lambda pkg, **kw: raw,
        )
        monkeypatch.setattr(
            "axm_ast.tools.search.SearchTool._format_symbol",
            staticmethod(lambda sym, mod_name: sym),
        )

    return _setup


# ── Unit: _format_text_header ──────────────────────────────────────────────


class TestFormatTextHeader:
    def test_text_header_name_filter(self):
        h = SearchTool._format_text_header(
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
        h = SearchTool._format_text_header(
            search_filters={
                "name": "x",
                "returns": None,
                "kind": "class",
                "inherits": None,
            },
            count=3,
        )
        assert re.search(r"name~.x.", h)
        assert "kind=class" in h
        assert "3 hits" in h

    def test_text_header_no_filters(self):
        h = SearchTool._format_text_header(
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
        h = SearchTool._format_text_header(
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


# ── Unit: _format_symbol_line ──────────────────────────────────────────────


class TestFormatSymbolLine:
    def test_format_function_line(self):
        sym = _func_dict("foo", "def foo(a: int, b: str) -> bool", ret="bool")
        line = SearchTool._format_symbol_line(sym)
        assert "foo" in line
        assert "bool" in line

    def test_format_class_line(self):
        sym = _class_dict("MyClass")
        line = SearchTool._format_symbol_line(sym)
        assert "MyClass" in line

    def test_format_variable_line_annotated(self):
        sym = _var_dict("x", annotation="int", value_repr="42")
        line = SearchTool._format_symbol_line(sym)
        assert "x" in line
        assert "int" in line
        assert "42" in line

    def test_format_variable_line_no_annotation(self):
        sym = _var_dict("y", value_repr="[]")
        line = SearchTool._format_symbol_line(sym)
        assert "y" in line
        assert "[]" in line


# ── Functional: text through _search ───────────────────────────────────────


class TestSearchText:
    def test_search_text_functions(self, patch_search):
        dicts = [
            _func_dict("search_items", "def search_items(q: str) -> list", ret="list"),
            _func_dict("search_all", "def search_all() -> None", ret="None"),
        ]
        patch_search(dicts)
        result = SearchTool._search(
            pkg=None,
            name="search",
            returns=None,
            kind=None,
            inherits=None,
        )
        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert lines[0].startswith("ast_search")
        assert "2 hits" in lines[0]
        assert "search_items(q: str) -> list" in result.text
        assert "search_all() -> None" in result.text

    def test_search_text_classes(self, patch_search):
        dicts = [_class_dict("SearchEngine"), _class_dict("SearchResult")]
        patch_search(dicts)
        result = SearchTool._search(
            pkg=None,
            name=None,
            returns=None,
            kind="class",
            inherits=None,
        )
        assert result.text is not None
        assert "SearchEngine" in result.text
        assert "SearchResult" in result.text
        # Classes rendered comma-separated on a single line
        for line in result.text.strip().splitlines()[1:]:
            if "SearchEngine" in line:
                assert "SearchResult" in line
                break

    def test_search_text_variables(self, patch_search):
        dicts = [_var_dict("max_count", annotation="int", value_repr="100")]
        patch_search(dicts)
        result = SearchTool._search(
            pkg=None,
            name=None,
            returns=None,
            kind="variable",
            inherits=None,
        )
        assert result.text is not None
        assert "max_count: int" in result.text

    def test_search_text_mixed(self, patch_search):
        dicts = [
            _func_dict("get_value", "def get_value(k: str) -> int", ret="int"),
            _class_dict("GetHelper"),
            _var_dict("get_default", annotation="str", value_repr='"x"'),
        ]
        patch_search(dicts)
        result = SearchTool._search(
            pkg=None,
            name="get",
            returns=None,
            kind=None,
            inherits=None,
        )
        text = result.text
        assert text is not None
        # Functions before classes before variables
        func_pos = text.index("get_value(")
        class_pos = text.index("GetHelper")
        var_pos = text.index("get_default")
        assert func_pos < class_pos < var_pos

    def test_search_text_empty(self, patch_search):
        patch_search([])
        result = SearchTool._search(
            pkg=None,
            name="zzz_nonexistent",
            returns=None,
            kind=None,
            inherits=None,
        )
        assert result.text is not None
        assert "0 hits" in result.text
        lines = result.text.strip().splitlines()
        assert len(lines) == 1

    def test_search_data_unchanged(self, patch_search):
        dicts = [
            _func_dict("search_items", "def search_items(q: str) -> list", ret="list"),
        ]
        patch_search(dicts)
        result = SearchTool._search(
            pkg=None,
            name="search",
            returns=None,
            kind=None,
            inherits=None,
        )
        assert result.data is not None
        assert "results" in result.data
        assert isinstance(result.data["results"], list)
        assert len(result.data["results"]) == 1
        entry = result.data["results"][0]
        assert entry["name"] == "search_items"
        assert entry["kind"] == "function"


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_return_type(self):
        sym = _func_dict("do_stuff", "def do_stuff(x: int)")
        line = SearchTool._format_symbol_line(sym)
        assert line == "do_stuff(x: int)"
        assert "->" not in line

    def test_very_long_signature(self):
        params = ", ".join(f"p{i}: str" for i in range(12))
        sig = f"def big({params}) -> None"
        sym = _func_dict("big", sig, ret="None")
        line = SearchTool._format_symbol_line(sym)
        assert line.startswith("big(")
        assert "-> None" in line
        assert "\n" not in line

    def test_variable_no_annotation_no_value(self):
        sym = _var_dict("x")
        line = SearchTool._format_symbol_line(sym)
        assert line == "x"

    def test_inherits_filter_in_header(self):
        h = SearchTool._format_text_header(
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
