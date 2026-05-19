"""Integration tests for SearchTool — validation against real packages."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.search import SearchTool
from tests.integration._helpers import _assert_tool_result, _make_func, _make_mod


@pytest.fixture()
def tool() -> SearchTool:
    """Provide a fresh SearchTool instance."""
    return SearchTool()


class TestSearchByKindUnit:
    """Unit-level kind validation tests (error path, no scan)."""

    def test_invalid_kind(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), kind="invalid_kind_xyz")
        assert result.success is False
        assert result.error is not None
        assert "Invalid kind" in result.error


@pytest.fixture()
def search_pkg(tmp_path: Path) -> Path:
    """Create a package with varied symbols for search tests."""
    pkg = tmp_path / "searchdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Search demo."""\n')
    (pkg / "funcs.py").write_text(
        '"""Functions module."""\n\n'
        "_TOLERANCE: float = 0.01\n"
        "MAX_RETRIES = 3\n\n\n"
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n\n\n'
        "def compute(x: int, y: int) -> int:\n"
        '    """Add two numbers."""\n'
        "    return x + y\n\n\n"
        "def _private() -> None:\n"
        '    """Internal."""\n'
    )
    (pkg / "models.py").write_text(
        '"""Models module."""\n\n'
        "from pydantic import BaseModel\n\n\n"
        "class User(BaseModel):\n"
        '    """A user model."""\n\n'
        "    name: str\n\n\n"
        "class Admin(BaseModel):\n"
        '    """Admin user."""\n\n'
        "    name: str\n"
        "    level: int = 1\n\n"
        "    @property\n"
        "    def is_admin(self) -> bool:\n"
        '        """Check admin."""\n'
        "        return True\n"
    )
    return pkg


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


def _make_pkg__from_search_suggestion(
    root: Path,
    modules: list[SimpleNamespace],
) -> SimpleNamespace:
    return SimpleNamespace(root=root, modules=modules)


class TestSearchByName:
    """Tests for name-based search."""

    def test_find_function(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), name="greet")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "greet" in names

    def test_find_class(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), name="User")
        assert result.success is True
        assert len(result.data["results"]) >= 1

    def test_no_results(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), name="nonexistent_xyz")
        assert result.success is True
        assert len(result.data["results"]) == 0


class TestSearchByReturnType:
    """Tests for return type filtering."""

    def test_filter_by_str_return(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), returns="str")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert len(names) >= 1
        assert "greet" in names

    def test_filter_by_int_return(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), returns="int")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "compute" in names


class TestSearchByKind:
    """Tests for kind-based filtering."""

    def test_filter_by_property(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), kind="property")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert len(names) >= 1
        assert "is_admin" in names

    def test_filter_by_class(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' returns only classes, not functions."""
        result = tool.execute(path=str(search_pkg), kind="class")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "User" in names
        assert "Admin" in names
        # Functions must not appear
        assert "greet" not in names
        assert "compute" not in names

    def test_filter_by_function(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='function' returns only top-level functions, not classes."""
        result = tool.execute(path=str(search_pkg), kind="function")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "greet" in names
        assert "compute" in names
        # Classes must not appear
        assert "User" not in names
        assert "Admin" not in names

    def test_filter_by_method(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='method' returns no results (fixture has no plain methods)."""
        result = tool.execute(path=str(search_pkg), kind="method")
        assert result.success is True
        # Fixture only has properties, not plain methods
        names = [s["name"] for s in result.data["results"]]
        assert "is_admin" not in names  # is_admin is a property, not a method

    def test_invalid_kind_lists_valid_values(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        """Error message lists all valid kind values."""
        result = tool.execute(path=str(search_pkg), kind="bogus")
        assert result.success is False
        assert result.error is not None
        assert "class" in result.error
        assert "function" in result.error
        assert "method" in result.error


class TestSearchByInheritance:
    """Tests for class base-class filtering."""

    def test_find_basemodel_subclasses(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        result = tool.execute(path=str(search_pkg), inherits="BaseModel")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert len(names) >= 2
        assert "User" in names
        assert "Admin" in names

    def test_no_subclasses(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), inherits="NonExistentBase")
        assert result.success is True
        assert len(result.data["results"]) == 0


class TestSearchEdgeCases:
    """Edge cases for SearchTool."""

    def test_empty_package(self, tool: SearchTool, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        result = tool.execute(path=str(pkg), name="anything")
        assert result.success is True
        assert len(result.data["results"]) == 0

    def test_no_filters_returns_all(self, tool: SearchTool, search_pkg: Path) -> None:
        """No filters should return all symbols (functions + classes)."""
        result = tool.execute(path=str(search_pkg))
        assert result.success is True
        assert len(result.data["results"]) > 0

    def test_kind_class_with_name(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' + name filter returns only matching classes."""
        result = tool.execute(path=str(search_pkg), kind="class", name="User")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "User" in names
        assert "Admin" not in names

    def test_kind_class_with_inherits(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' + inherits filter works."""
        result = tool.execute(path=str(search_pkg), kind="class", inherits="BaseModel")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "User" in names
        assert "Admin" in names

    def test_kind_class_with_returns(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' + returns filter gives empty (classes have no return type)."""
        result = tool.execute(path=str(search_pkg), kind="class", returns="str")
        assert result.success is True
        assert len(result.data["results"]) == 0


class TestSearchVariables:
    """Tests for variable/constant search via SearchTool."""

    def test_search_variable_by_name(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='variable' + name returns the matching constant."""
        result = tool.execute(path=str(search_pkg), kind="variable", name="_TOLERANCE")
        assert result.success is True
        assert len(result.data["results"]) == 1
        sym = result.data["results"][0]
        assert sym["name"] == "_TOLERANCE"
        assert sym["kind"] == "variable"
        assert sym["annotation"] == "float"
        assert sym["value_repr"] == "0.01"

    def test_search_variable_kind_filter(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        """kind='variable' returns only variables, no functions or classes."""
        result = tool.execute(path=str(search_pkg), kind="variable")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "greet" not in names
        assert "User" not in names
        # At least the two constants we added
        assert "_TOLERANCE" in names
        assert "MAX_RETRIES" in names

    def test_search_kind_none_includes_variables(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        """No kind filter returns functions, methods, AND variables."""
        result = tool.execute(path=str(search_pkg))
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "greet" in names
        assert "_TOLERANCE" in names

    def test_search_variable_with_returns_empty(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        """kind='variable' + returns filter gives empty (variables have no return)."""
        result = tool.execute(path=str(search_pkg), kind="variable", returns="float")
        assert result.success is True
        assert len(result.data["results"]) == 0

    def test_search_function_unchanged(
        self, tool: SearchTool, search_pkg: Path
    ) -> None:
        """kind='function' still works correctly after variable support."""
        result = tool.execute(path=str(search_pkg), kind="function")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "greet" in names
        assert "_TOLERANCE" not in names
        assert "User" not in names

    def test_search_class_unchanged(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' still works correctly after variable support."""
        result = tool.execute(path=str(search_pkg), kind="class")
        assert result.success is True
        names = [s["name"] for s in result.data["results"]]
        assert "User" in names
        assert "_TOLERANCE" not in names
        assert "greet" not in names

    def test_kind_class_no_match(self, tool: SearchTool, search_pkg: Path) -> None:
        """kind='class' with non-matching name returns empty list."""
        result = tool.execute(path=str(search_pkg), kind="class", name="nonexistent")
        assert result.success is True
        assert len(result.data["results"]) == 0


def test_search_tool_exception(tmp_path: Path, mocker: MagicMock) -> None:
    from axm_ast.tools.search import SearchTool

    pkg = _make_pkg(tmp_path, {"__init__.py": ""})
    mocker.patch(
        "axm_ast.core.cache.get_package",
        side_effect=RuntimeError("search boom"),
    )
    result = SearchTool().execute(path=str(pkg), pattern="foo")
    assert result.success is False
    assert "search boom" in (result.error or "")


def test_suggestion_module_populated(tmp_path: Path) -> None:
    """Suggestions must have a non-None module even when mod.name is None."""
    root = tmp_path / "src" / "mypkg"
    root.mkdir(parents=True)
    mod_path = root / "helpers.py"
    mod_path.touch()

    mod = _make_mod(
        path=mod_path,
        name=None,
        functions=[_make_func("compute_score")],
    )
    pkg = _make_pkg__from_search_suggestion(root=root, modules=[mod])

    # Query with a typo so fuzzy matching kicks in
    suggestions = SearchTool.find_suggestions(pkg, "compute_scor")

    assert len(suggestions) >= 1
    for s in suggestions:
        assert s["module"] is not None, "suggestion module must not be None"


def test_suggestion_module_uses_mod_name_when_set(tmp_path: Path) -> None:
    """When mod.name is already set, it is used directly (no fallback)."""
    root = tmp_path / "src" / "mypkg"
    root.mkdir(parents=True)
    mod_path = root / "utils.py"
    mod_path.touch()

    explicit_name = "mypkg.utils"
    mod = _make_mod(
        path=mod_path,
        name=explicit_name,
        functions=[_make_func("do_stuff")],
    )
    pkg = _make_pkg__from_search_suggestion(root=root, modules=[mod])

    suggestions = SearchTool.find_suggestions(pkg, "do_stuf")

    assert len(suggestions) >= 1
    assert suggestions[0]["module"] == explicit_name


def test_suggestion_empty_package(tmp_path: Path) -> None:
    """Package with no modules returns empty suggestions without crashing."""
    pkg = _make_pkg__from_search_suggestion(root=tmp_path, modules=[])

    suggestions = SearchTool.find_suggestions(pkg, "anything")

    assert suggestions == []


class TestSearchToolIntegration:
    """Tests for ast_search tool."""

    def test_search_by_name(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), name="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "results" in result.data
        assert len(result.data["results"]) >= 1

    def test_search_by_returns(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), returns="str")
        assert result.success is True
        assert len(result.data["results"]) >= 1

    def test_search_no_results(self, sample_project: Path) -> None:
        from axm_ast.tools.search import SearchTool

        tool = SearchTool()
        result = tool.execute(
            path=str(sample_project / "src" / "demo"), name="nonexistent_xyz"
        )
        assert result.success is True
        assert len(result.data["results"]) == 0


def _suggestion(name: str, score: float, kind: str, module: str) -> dict[str, Any]:
    return {"name": name, "score": score, "kind": kind, "module": module}


class TestSearchWithSuggestions:
    """Functional tests for suggestions wired into ast_search."""

    def test_search_with_suggestions_text(self, tmp_path: Path) -> None:
        """Zero results + suggestions produces header and ?-prefixed lines (AC5)."""
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
            _suggestion("get_sessions", 0.85, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search.find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool().execute(path=str(tmp_path), name="get_sesion")

        assert result.text is not None
        assert "suggestion" in result.text.lower()
        lines = result.text.strip().splitlines()
        suggestion_lines = [ln for ln in lines if ln.startswith("?")]
        assert len(suggestion_lines) >= 2

    def test_search_with_results_no_suggestions(self, tmp_path: Path) -> None:
        """When results exist, no suggestions key in data (AC3)."""
        func = _make_func("search_symbols")
        with patch(
            "axm_ast.core.analyzer.search_symbols",
            return_value=[("core.analyzer", func)],
        ):
            result = SearchTool().execute(path=str(tmp_path), name="search")

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_no_name_no_suggestions(self, tmp_path: Path) -> None:
        """When name is None and no results, no suggestions key (AC4)."""
        with patch("axm_ast.core.analyzer.search_symbols", return_value=[]):
            result = SearchTool().execute(path=str(tmp_path))

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_suggestions_data_shape(self, tmp_path: Path) -> None:
        """Suggestions data has correct shape alongside empty results (AC4)."""
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search.find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool().execute(path=str(tmp_path), name="get_sesion")

        assert result.data["results"] == []
        assert "suggestions" in result.data
        assert isinstance(result.data["suggestions"], list)
        for s in result.data["suggestions"]:
            assert "name" in s
            assert "score" in s
            assert "kind" in s
            assert "module" in s


class TestSearchResultNoCountKeyIntegration:
    """Integration-scope sibling: empty-result path."""

    @patch.object(SearchTool, "format_symbol", return_value={"name": "X"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_empty_results_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty search results should return data={'results': []} with no count key."""
        mock_search.return_value = []

        result = SearchTool().execute(path=str(tmp_path), name="NonExistent")

        assert result.success is True
        assert result.data == {"results": []}
        assert "count" not in result.data


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
