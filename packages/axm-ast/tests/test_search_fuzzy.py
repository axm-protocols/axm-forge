"""Tests for fuzzy suggestion feature in ast_search."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from axm_ast.tools.search import SearchTool, _find_suggestions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_func(name: str, kind_value: str = "function") -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.kind = MagicMock()
    fn.kind.value = kind_value
    fn.return_type = None
    fn.parameters = []
    fn.decorators = []
    fn.docstring = None
    return fn


def _make_class(name: str, methods: list[MagicMock] | None = None) -> MagicMock:
    cls = MagicMock()
    cls.name = name
    cls.methods = methods or []
    cls.bases = []
    cls.decorators = []
    cls.docstring = None
    return cls


def _make_var(name: str) -> MagicMock:
    var = MagicMock()
    var.name = name
    var.type_annotation = None
    return var


def _make_module(
    name: str,
    *,
    functions: list[MagicMock] | None = None,
    classes: list[MagicMock] | None = None,
    variables: list[MagicMock] | None = None,
) -> MagicMock:
    mod = MagicMock()
    mod.name = name
    mod.functions = functions or []
    mod.classes = classes or []
    mod.variables = variables or []
    return mod


def _make_pkg(*modules: MagicMock) -> MagicMock:
    pkg = MagicMock()
    pkg.modules = list(modules)
    return pkg


def _suggestion(name: str, score: float, kind: str, module: str) -> dict[str, Any]:
    return {"name": name, "score": score, "kind": kind, "module": module}


# ---------------------------------------------------------------------------
# Unit tests — _find_suggestions
# ---------------------------------------------------------------------------


class TestFindSuggestions:
    """Unit tests for _find_suggestions."""

    def test_find_suggestions_typo(self) -> None:
        """Typo query returns close match with high score."""
        mod = _make_module(
            "core.session",
            functions=[_make_func("get_session"), _make_func("get_value")],
        )
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="get_sesion")

        names = [s["name"] for s in suggestions]
        assert "get_session" in names
        match = next(s for s in suggestions if s["name"] == "get_session")
        assert match["score"] >= 0.8

    def test_find_suggestions_case_insensitive(self) -> None:
        """Case-insensitive matching finds PascalCase symbols."""
        mod = _make_module(
            "core.models",
            classes=[_make_class("ToolResult"), _make_class("FunctionInfo")],
        )
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="toolresult")

        names = [s["name"] for s in suggestions]
        assert "ToolResult" in names

    def test_find_suggestions_no_match(self) -> None:
        """Completely unrelated query returns empty list."""
        mod = _make_module(
            "core.utils",
            functions=[_make_func("foo"), _make_func("bar")],
        )
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="zzzzz")

        assert suggestions == []

    def test_find_suggestions_kind_filter(self) -> None:
        """Kind filter restricts suggestions to that kind only (AC7)."""
        mod = _make_module(
            "core.search",
            functions=[_make_func("search")],
            classes=[_make_class("Searcher")],
        )
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="serch", kind="class")

        names = [s["name"] for s in suggestions]
        assert "Searcher" in names
        assert "search" not in names

    def test_find_suggestions_dedup(self) -> None:
        """Same symbol in multiple modules appears once (AC8)."""
        mod1 = _make_module("mod_a", functions=[_make_func("get_value")])
        mod2 = _make_module("mod_b", functions=[_make_func("get_value")])
        mod3 = _make_module("mod_c", functions=[_make_func("get_value")])
        pkg = _make_pkg(mod1, mod2, mod3)

        suggestions = _find_suggestions(pkg, name="get_valu")

        value_suggestions = [s for s in suggestions if s["name"] == "get_value"]
        assert len(value_suggestions) == 1


# ---------------------------------------------------------------------------
# Unit tests — rendering
# ---------------------------------------------------------------------------


class TestRenderSuggestions:
    """Unit tests for suggestion text rendering."""

    def test_render_suggestion_line(self) -> None:
        """Suggestion line starts with ? and contains score and kind."""
        suggestion = _suggestion("get_session", 0.92, "function", "core.analyzer")

        line = SearchTool._render_suggestion_line(suggestion)

        assert line.startswith("?")
        assert ".92" in line
        assert "func" in line
        assert "core.analyzer" in line

    def test_render_suggestions_header(self) -> None:
        """Header shows 0 hits and suggestion count."""
        header = SearchTool._format_text_header(
            search_filters={
                "name": "get_sesion",
                "returns": None,
                "kind": None,
                "inherits": None,
            },
            count=0,
            suggestion_count=3,
        )

        assert "0 hits" in header
        assert "3 suggestions" in header


# ---------------------------------------------------------------------------
# Functional tests — SearchTool._search integration
# ---------------------------------------------------------------------------


class TestSearchWithSuggestions:
    """Functional tests for suggestions wired into _search."""

    def test_search_with_suggestions_text(self) -> None:
        """Zero results + suggestions produces header and ?-prefixed lines (AC5)."""
        pkg = _make_pkg()
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
            _suggestion("get_sessions", 0.85, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search._find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool._search(
                pkg, name="get_sesion", returns=None, kind=None, inherits=None
            )

        assert result.text is not None
        assert "suggestion" in result.text.lower()
        lines = result.text.strip().splitlines()
        suggestion_lines = [ln for ln in lines if ln.startswith("?")]
        assert len(suggestion_lines) >= 2

    def test_search_with_results_no_suggestions(self) -> None:
        """When results exist, no suggestions key in data (AC3)."""
        func = _make_func("search_symbols")
        pkg = _make_pkg()
        with patch(
            "axm_ast.core.analyzer.search_symbols",
            return_value=[("core.analyzer", func)],
        ):
            result = SearchTool._search(
                pkg, name="search", returns=None, kind=None, inherits=None
            )

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_no_name_no_suggestions(self) -> None:
        """When name is None and no results, no suggestions key (AC4)."""
        pkg = _make_pkg()
        with patch("axm_ast.core.analyzer.search_symbols", return_value=[]):
            result = SearchTool._search(
                pkg, name=None, returns=None, kind=None, inherits=None
            )

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_suggestions_data_shape(self) -> None:
        """Suggestions data has correct shape alongside empty results (AC4)."""
        pkg = _make_pkg()
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search._find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool._search(
                pkg, name="get_sesion", returns=None, kind=None, inherits=None
            )

        assert result.data["results"] == []
        assert "suggestions" in result.data
        assert isinstance(result.data["suggestions"], list)
        for s in result.data["suggestions"]:
            assert "name" in s
            assert "score" in s
            assert "kind" in s
            assert "module" in s


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFindSuggestionsEdgeCases:
    """Edge case tests for _find_suggestions."""

    def test_empty_package(self) -> None:
        """Empty package with no modules returns empty suggestions."""
        pkg = _make_pkg()

        suggestions = _find_suggestions(pkg, name="anything")

        assert suggestions == []

    def test_very_short_query(self) -> None:
        """Very short query still works without crash."""
        mod = _make_module(
            "core.utils",
            functions=[_make_func("a_func"), _make_func("b_func")],
        )
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="a")

        assert isinstance(suggestions, list)

    def test_exact_match_kind_mismatch(self) -> None:
        """Exact name but wrong kind yields no suggestions per AC7."""
        mod = _make_module(
            "core.models",
            classes=[_make_class("Foo")],
        )
        pkg = _make_pkg(mod)

        # kind="function" but Foo is a class → filtered out by AC7
        suggestions = _find_suggestions(pkg, name="Foo", kind="function")

        assert suggestions == []

    def test_method_names(self) -> None:
        """Method names like ClassName.validate are suggested."""
        validate_method = _make_func("validate", kind_value="method")
        cls = _make_class("MyClass", methods=[validate_method])
        mod = _make_module("core.models", classes=[cls])
        pkg = _make_pkg(mod)

        suggestions = _find_suggestions(pkg, name="validat")

        names = [s["name"] for s in suggestions]
        assert any("validate" in n for n in names)
