"""Unit tests for SearchTool (src/axm_ast/tools/search.py)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    VariableInfo,
)
from axm_ast.tools.search import SearchTool, _find_suggestions

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def tool() -> SearchTool:
    """Provide a fresh SearchTool instance."""
    return SearchTool()


@pytest.fixture()
def function_symbol() -> FunctionInfo:
    return FunctionInfo(
        name="greet",
        signature="(name: str) -> str",
        return_type="str",
        kind=FunctionKind.FUNCTION,
        line_start=5,
        line_end=7,
        decorators=[],
    )


@pytest.fixture()
def class_symbol() -> ClassInfo:
    return ClassInfo(
        name="Greeter",
        bases=["object"],
        line_start=10,
        line_end=20,
        decorators=[],
        methods=[],
    )


@pytest.fixture()
def variable_symbol() -> VariableInfo:
    return VariableInfo(
        name="VERSION",
        line=1,
        annotation="str",
        value_repr='"1.0"',
    )


@pytest.fixture()
def function_sym() -> dict[str, Any]:
    return {
        "name": "do_work",
        "kind": "function",
        "signature": "def do_work(a: int, b: str) -> bool",
        "return_type": "bool",
    }


@pytest.fixture()
def class_sym() -> dict[str, Any]:
    return {"name": "MyClass", "kind": "class"}


@pytest.fixture()
def variable_sym_annotated() -> dict[str, Any]:
    return {
        "name": "timeout",
        "kind": "variable",
        "annotation": "int",
        "value_repr": "30",
    }


@pytest.fixture
def _mock_pkg() -> MagicMock:
    return MagicMock()


# ── Helpers (fuzzy suggestions) ───────────────────────────────────────────


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


def _make_suggestion(
    name: str = "get_session",
    score: float = 0.92,
    kind: str = "function",
    module: str | None = None,
) -> dict[str, Any]:
    return {"name": name, "score": score, "kind": kind, "module": module}


# ── Tool identity ─────────────────────────────────────────────────────────


class TestSearchToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: SearchTool) -> None:
        assert tool.name == "ast_search"

    def test_has_agent_hint(self, tool: SearchTool) -> None:
        assert tool.agent_hint


class TestSearchEdgeCasesUnit:
    """Unit-level edge cases for SearchTool (no real I/O)."""

    def test_bad_path(self, tool: SearchTool) -> None:
        result = tool.execute(path="/nonexistent/path", name="foo")
        assert result.success is False


# ── _validate_kind ────────────────────────────────────────────────────────


class TestValidateKind:
    """SearchTool._validate_kind — kind string → SymbolKind | ToolResult | None."""

    def test_valid_kind_returns_enum(self, tool: SearchTool) -> None:
        from axm_ast.models import SymbolKind

        result = tool._validate_kind("function")
        assert result == SymbolKind("function")

    def test_each_valid_kind_accepted(self, tool: SearchTool) -> None:
        from axm_ast.models import SymbolKind

        for kind in SymbolKind:
            assert tool._validate_kind(kind.value) == kind

    def test_invalid_kind_returns_error_result(self, tool: SearchTool) -> None:
        result = tool._validate_kind("nonexistent")
        assert isinstance(result, ToolResult)
        assert not result.success
        assert result.error is not None
        assert "Invalid kind" in result.error

    def test_none_returns_none(self, tool: SearchTool) -> None:
        assert tool._validate_kind(None) is None


# ── _format_symbol ────────────────────────────────────────────────────────


class TestFormatSymbolModuleName:
    """_format_symbol must receive and include the module name."""

    def test_format_symbol_includes_module_name(
        self, function_symbol: FunctionInfo
    ) -> None:
        entry = SearchTool._format_symbol(function_symbol, "pkg.utils")
        assert entry["module"] == "pkg.utils"

    def test_format_symbol_module_never_empty(
        self,
        function_symbol: FunctionInfo,
        class_symbol: ClassInfo,
        variable_symbol: VariableInfo,
    ) -> None:
        symbols: list[tuple[FunctionInfo | ClassInfo | VariableInfo, str]] = [
            (function_symbol, "pkg.funcs"),
            (class_symbol, "pkg.classes"),
            (variable_symbol, "pkg.consts"),
        ]
        for sym, mod_name in symbols:
            entry = SearchTool._format_symbol(sym, mod_name)
            assert entry["module"] != "", f"module empty for {sym.name}"
            assert entry["module"] == mod_name


class TestFormatSymbol:
    """SearchTool._format_symbol — AST symbol → serialized dict."""

    def test_always_includes_name_and_module(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="foo")
        entry = tool._format_symbol(sym, "pkg.bar")
        assert entry["name"] == "foo"
        assert entry["module"] == "pkg.bar"

    def test_includes_signature_when_present(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="f", signature="(x: int) -> str")
        entry = tool._format_symbol(sym, "m")
        assert entry["signature"] == "(x: int) -> str"

    def test_omits_signature_when_absent(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="f")
        entry = tool._format_symbol(sym, "m")
        assert "signature" not in entry

    def test_includes_return_type_when_present(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="f", return_type="bool")
        entry = tool._format_symbol(sym, "m")
        assert entry["return_type"] == "bool"

    def test_omits_return_type_when_absent(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="f")
        entry = tool._format_symbol(sym, "m")
        assert "return_type" not in entry

    def test_variable_sets_kind_field(self, tool: SearchTool) -> None:
        sym = SimpleNamespace(name="V", value_repr="42")
        entry = tool._format_symbol(sym, "m")
        assert entry["kind"] == "variable"

    def test_variable_info_includes_annotation(self, tool: SearchTool) -> None:
        sym = MagicMock(spec=VariableInfo)
        sym.name = "V"
        sym.value_repr = "42"
        sym.annotation = "int"
        entry = tool._format_symbol(sym, "m")
        assert entry["annotation"] == "int"
        assert entry["value_repr"] == "42"

    def test_variable_info_omits_falsy_fields(self, tool: SearchTool) -> None:
        sym = MagicMock(spec=VariableInfo)
        sym.name = "V"
        sym.value_repr = ""
        sym.annotation = ""
        entry = tool._format_symbol(sym, "m")
        assert "annotation" not in entry
        assert "value_repr" not in entry


def test_format_symbol_dict() -> None:
    # FunctionInfo
    func = MagicMock(spec=FunctionInfo)
    func.name = "run"
    func.signature = "def run(self) -> None"
    func.return_type = "None"
    func.kind = MagicMock()
    func.kind.value = "method"
    result_func = SearchTool._format_symbol(func, "my_module")
    assert result_func["name"] == "run"
    assert result_func["module"] == "my_module"
    assert result_func["signature"] == "def run(self) -> None"
    assert result_func["return_type"] == "None"
    assert result_func["kind"] == "method"

    # ClassInfo
    cls = MagicMock(spec=ClassInfo)
    cls.name = "Widget"
    result_cls = SearchTool._format_symbol(cls, "widgets")
    assert result_cls["name"] == "Widget"
    assert result_cls["kind"] == "class"

    # VariableInfo
    var = MagicMock(spec=VariableInfo)
    var.name = "MAX"
    var.annotation = "int"
    var.value_repr = "100"
    result_var = SearchTool._format_symbol(var, "constants")
    assert result_var["name"] == "MAX"
    assert result_var["kind"] == "variable"
    assert result_var["annotation"] == "int"
    assert result_var["value_repr"] == "100"


# ── kind filter ───────────────────────────────────────────────────────────


def test_function_has_kind() -> None:
    sym = SimpleNamespace(name="f", signature="def f()", kind="function")
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "function"


def test_method_has_kind() -> None:
    sym = SimpleNamespace(name="m", signature="def m(self)", kind="method")
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "method"


def test_class_has_kind() -> None:
    sym = ClassInfo(name="C", line_start=1, line_end=10)
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "class"


def test_variable_still_has_kind() -> None:
    sym = SimpleNamespace(name="V", value_repr="42")
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "variable"


def test_property_kind() -> None:
    sym = FunctionInfo(
        name="prop",
        kind=FunctionKind.PROPERTY,
        line_start=1,
        line_end=3,
    )
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "property"


def test_abstract_method_kind() -> None:
    sym = FunctionInfo(
        name="do_thing",
        kind=FunctionKind.ABSTRACT,
        line_start=5,
        line_end=8,
    )
    entry = SearchTool._format_symbol(sym, "mod")
    assert entry["kind"] == "abstract"


# ── format (_format_symbol_line, _render_text) ────────────────────────────


def test_format_symbol_line_function(function_sym: dict[str, Any]) -> None:
    result = SearchTool._format_symbol_line(function_sym)
    assert result == "do_work(a: int, b: str) -> bool"


def test_format_symbol_line_class(class_sym: dict[str, Any]) -> None:
    result = SearchTool._format_symbol_line(class_sym)
    assert result == "MyClass"


def test_format_symbol_line_variable_annotated(
    variable_sym_annotated: dict[str, Any],
) -> None:
    result = SearchTool._format_symbol_line(variable_sym_annotated)
    assert result == "timeout: int = 30"


def test_render_text_mixed(
    function_sym: dict[str, Any],
    class_sym: dict[str, Any],
    variable_sym_annotated: dict[str, Any],
) -> None:
    symbols = [function_sym, class_sym, variable_sym_annotated]
    result = SearchTool._render_text(
        symbols,
        search_filters={"name": None, "returns": None, "kind": None, "inherits": None},
    )
    lines = result.split("\n")
    # First line is the header
    assert "3 hits" in lines[0]
    # Functions appear before classes, classes before variables
    func_idx = next(i for i, line in enumerate(lines) if "do_work" in line)
    cls_idx = next(i for i, line in enumerate(lines) if "MyClass" in line)
    var_idx = next(i for i, line in enumerate(lines) if "timeout" in line)
    assert func_idx < cls_idx < var_idx


def test_format_symbol_line_no_params_in_signature() -> None:
    """Signature without parentheses falls back to ()."""
    sym: dict[str, Any] = {
        "name": "ping",
        "kind": "function",
        "signature": "def ping",
        "return_type": None,
    }
    result = SearchTool._format_symbol_line(sym)
    assert result == "ping()"


def test_format_symbol_line_nested_parens() -> None:
    """Nested parens in type hints are matched correctly."""
    sym: dict[str, Any] = {
        "name": "f",
        "kind": "function",
        "signature": "def f(x: dict[str, list[int]])",
        "return_type": None,
    }
    result = SearchTool._format_symbol_line(sym)
    assert result == "f(x: dict[str, list[int]])"


def test_format_symbol_line_variable_bare() -> None:
    """Variable with no annotation or value returns just the name."""
    sym: dict[str, Any] = {"name": "flag", "kind": "variable"}
    result = SearchTool._format_symbol_line(sym)
    assert result == "flag"


# ── count (no 'count' key in result.data) ─────────────────────────────────


class TestSearchResultNoCountKey:
    """Verify that _search does not include a 'count' key in result.data."""

    @patch.object(SearchTool, "_format_symbol", return_value={"name": "Foo"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_result_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        _mock_pkg: MagicMock,
    ) -> None:
        """Run a search and assert 'count' is not in result.data."""
        mock_search.return_value = [("mod", MagicMock())]

        result = SearchTool._search(
            _mock_pkg, name="Foo", returns=None, kind=None, inherits=None
        )

        assert result.success is True
        assert "count" not in result.data
        assert "results" in result.data
        assert len(result.data["results"]) == 1

    @patch.object(SearchTool, "_format_symbol", return_value={"name": "X"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_empty_results_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        _mock_pkg: MagicMock,
    ) -> None:
        """Empty search results should return data={'results': []} with no count key."""
        mock_search.return_value = []

        result = SearchTool._search(
            _mock_pkg, name="NonExistent", returns=None, kind=None, inherits=None
        )

        assert result.success is True
        assert result.data == {"results": []}
        assert "count" not in result.data


# ── _find_suggestions ─────────────────────────────────────────────────────


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

        # Single-char query: must not crash; may return empty (below cutoff)
        assert suggestions == [] or all("name" in s for s in suggestions)

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


# ── _format_text_header ───────────────────────────────────────────────────


class TestRenderSuggestionsHeader:
    """Unit tests for header rendering when suggestions are present."""

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


# ── render_suggestion_line ────────────────────────────────────────────────


class TestRenderSuggestionLineWithModule:
    """_render_suggestion_line — compact format including module."""

    def test_render_suggestion_line(self) -> None:
        """Suggestion line uses compact format with no padding."""
        suggestion = _suggestion("get_session", 0.92, "function", "core.analyzer")

        line = SearchTool._render_suggestion_line(suggestion)

        assert line == "? get_session .92 func core.analyzer"


def test_render_suggestion_line_compact() -> None:
    """module=None produces no trailing None."""
    suggestion = _make_suggestion(module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? get_session .92 func"


def test_render_suggestion_line_with_module() -> None:
    """module present is appended after kind."""
    suggestion = _make_suggestion(module="core.analyzer")
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? get_session .92 func core.analyzer"


def test_render_suggestion_line_no_padding() -> None:
    """Short name has no extra whitespace padding."""
    suggestion = _make_suggestion(name="foo", score=0.75)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? foo .75 func"


def test_render_suggestion_line_long_name() -> None:
    """Very long name (31 chars) is not truncated."""
    suggestion = _make_suggestion(
        name="SearchTool._collect_module_candidates", module=None
    )
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? SearchTool._collect_module_candidates .92 func"


def test_render_suggestion_line_perfect_score() -> None:
    """Score 1.0 renders as '1.0', not '.100'."""
    suggestion = _make_suggestion(name="exact_match", score=1.0, module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? exact_match 1.0 func"


def test_render_suggestion_line_short_kind() -> None:
    """Kind shorter than 4 chars rendered as-is, no padding."""
    suggestion = _make_suggestion(name="foo", kind="cls", module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? foo .92 cls"
