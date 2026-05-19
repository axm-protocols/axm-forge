"""Integration tests for search_text rendering (real I/O via public surface)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from axm_ast.tools.search import SearchTool


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
    """Patch search_symbols + format_symbol so execute() returns controlled dicts."""

    def _setup(formatted_dicts: list[dict[str, Any]]) -> None:
        raw = [(d.get("module", "mod"), d) for d in formatted_dicts]
        monkeypatch.setattr(
            "axm_ast.core.analyzer.search_symbols",
            lambda pkg, **kw: raw,
        )
        monkeypatch.setattr(
            "axm_ast.tools.search.SearchTool.format_symbol",
            staticmethod(lambda sym, mod_name: sym),
        )

    return _setup


class TestSearchText:
    def test_search_text_functions(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        dicts = [
            _func_dict("search_items", "def search_items(q: str) -> list", ret="list"),
            _func_dict("search_all", "def search_all() -> None", ret="None"),
        ]
        patch_search(dicts)
        result = SearchTool().execute(
            path=str(tmp_path),
            name="search",
        )
        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert lines[0].startswith("ast_search")
        assert "2 hits" in lines[0]
        assert "search_items(q: str) -> list" in result.text
        assert "search_all() -> None" in result.text

    def test_search_text_classes(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        dicts = [_class_dict("SearchEngine"), _class_dict("SearchResult")]
        patch_search(dicts)
        result = SearchTool().execute(
            path=str(tmp_path),
            kind="class",
        )
        assert result.text is not None
        assert "SearchEngine" in result.text
        assert "SearchResult" in result.text
        # Classes rendered comma-separated on a single line
        for line in result.text.strip().splitlines()[1:]:
            if "SearchEngine" in line:
                assert "SearchResult" in line
                break

    def test_search_text_variables(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        dicts = [_var_dict("max_count", annotation="int", value_repr="100")]
        patch_search(dicts)
        result = SearchTool().execute(
            path=str(tmp_path),
            kind="variable",
        )
        assert result.text is not None
        assert "max_count: int" in result.text

    def test_search_text_mixed(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        dicts = [
            _func_dict("get_value", "def get_value(k: str) -> int", ret="int"),
            _class_dict("GetHelper"),
            _var_dict("get_default", annotation="str", value_repr='"x"'),
        ]
        patch_search(dicts)
        result = SearchTool().execute(
            path=str(tmp_path),
            name="get",
        )
        text = result.text
        assert text is not None
        # Functions before classes before variables
        func_pos = text.index("get_value(")
        class_pos = text.index("GetHelper")
        var_pos = text.index("get_default")
        assert func_pos < class_pos < var_pos

    def test_search_text_empty(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        patch_search([])
        result = SearchTool().execute(
            path=str(tmp_path),
            name="zzz_nonexistent",
        )
        assert result.text is not None
        assert "0 hits" in result.text
        lines = result.text.strip().splitlines()
        assert len(lines) == 1

    def test_search_data_unchanged(
        self,
        patch_search: Callable[[list[dict[str, Any]]], None],
        tmp_path: Path,
    ) -> None:
        dicts = [
            _func_dict("search_items", "def search_items(q: str) -> list", ret="list"),
        ]
        patch_search(dicts)
        result = SearchTool().execute(
            path=str(tmp_path),
            name="search",
        )
        assert result.data is not None
        assert "results" in result.data
        assert isinstance(result.data["results"], list)
        assert len(result.data["results"]) == 1
        entry = result.data["results"][0]
        assert entry["name"] == "search_items"
        assert entry["kind"] == "function"
