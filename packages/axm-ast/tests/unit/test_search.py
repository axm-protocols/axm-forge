"""Unit tests for SearchTool — pure identity and validation, no scan I/O."""

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


class TestSearchToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: SearchTool) -> None:
        assert tool.name == "ast_search"

    def test_has_agent_hint(self, tool: SearchTool) -> None:
        assert tool.agent_hint


class TestSearchByKindUnit:
    """Unit-level kind validation tests (error path, no scan)."""

    def test_invalid_kind(self, tool: SearchTool, search_pkg: Path) -> None:
        result = tool.execute(path=str(search_pkg), kind="invalid_kind_xyz")
        assert result.success is False
        assert result.error is not None
        assert "Invalid kind" in result.error
