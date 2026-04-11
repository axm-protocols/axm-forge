"""Tests for SearchTool — semantic symbol search via MCP tool wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.search import SearchTool


@pytest.fixture()
def tool() -> SearchTool:
    """Provide a fresh SearchTool instance."""
    return SearchTool()


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


# ─── Tool identity ──────────────────────────────────────────────────────────


class TestSearchToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: SearchTool) -> None:
        assert tool.name == "ast_search"

    def test_has_agent_hint(self, tool: SearchTool) -> None:
        assert tool.agent_hint


# ─── Search by name ─────────────────────────────────────────────────────────


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


# ─── Search by return type ───────────────────────────────────────────────────


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


# ─── Search by kind ──────────────────────────────────────────────────────────


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

    def test_invalid_kind(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), kind="invalid_kind_xyz")
        assert result.success is False
        assert result.error is not None
        assert "Invalid kind" in result.error

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


# ─── Search by inheritance ───────────────────────────────────────────────────


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


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestSearchEdgeCases:
    """Edge cases for SearchTool."""

    def test_bad_path(self, tool: SearchTool) -> None:
        result = tool.execute(path="/nonexistent/path", name="foo")
        assert result.success is False

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


# ─── Variable search ─────────────────────────────────────────────────────────


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
