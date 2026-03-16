"""Tests for DeadCodeTool — dead code detection via MCP tool wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.dead_code import DeadCodeTool


@pytest.fixture()
def tool() -> DeadCodeTool:
    """Provide a fresh DeadCodeTool instance."""
    return DeadCodeTool()


@pytest.fixture()
def dead_pkg(tmp_path: Path) -> Path:
    """Create a package with intentional dead code."""
    pkg = tmp_path / "deadcodedemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Dead code demo."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        "def used_function() -> str:\n"
        '    """Used."""\n'
        '    return "ok"\n\n\n'
        "def unused_function() -> str:\n"
        '    """Not called anywhere."""\n'
        '    return "dead"\n\n\n'
        "class UsedClass:\n"
        '    """Used class."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run method."""\n'
        "        used_function()\n"
    )
    return pkg


# ─── Tool identity ──────────────────────────────────────────────────────────


class TestDeadCodeToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: DeadCodeTool) -> None:
        assert tool.name == "ast_dead_code"


# ─── Execute ─────────────────────────────────────────────────────────────────


class TestDeadCodeToolExecute:
    """Tests for DeadCodeTool.execute."""

    def test_returns_result(self, tool: DeadCodeTool, dead_pkg: Path) -> None:
        result = tool.execute(path=str(dead_pkg))
        assert result.success is True
        assert "dead_symbols" in result.data
        assert "total" in result.data

    def test_detects_unused_function(self, tool: DeadCodeTool, dead_pkg: Path) -> None:
        result = tool.execute(path=str(dead_pkg))
        assert result.success is True
        names = [s["name"] for s in result.data["dead_symbols"]]
        assert "unused_function" in names

    def test_clean_package(self, tool: DeadCodeTool, tmp_path: Path) -> None:
        """Package with no dead code → empty list."""
        pkg = tmp_path / "clean"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Clean."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\n\n'
            '__all__ = ["greet"]\n\n\n'
            "def greet() -> str:\n"
            '    """Say hi."""\n'
            '    return "hi"\n'
        )
        result = tool.execute(path=str(pkg))
        assert result.success is True
        assert result.data["total"] == 0


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestDeadCodeToolEdgeCases:
    """Edge cases for DeadCodeTool."""

    def test_bad_path(self, tool: DeadCodeTool) -> None:
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False

    def test_not_a_directory(self, tool: DeadCodeTool, tmp_path: Path) -> None:
        f = tmp_path / "file.py"
        f.write_text("x = 1\n")
        result = tool.execute(path=str(f))
        assert result.success is False
        assert result.error is not None
        assert "Not a directory" in result.error

    def test_include_tests_option(self, tool: DeadCodeTool, dead_pkg: Path) -> None:
        result = tool.execute(path=str(dead_pkg), include_tests=True)
        assert result.success is True
        assert isinstance(result.data["dead_symbols"], list)
