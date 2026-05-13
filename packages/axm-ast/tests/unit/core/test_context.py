"""Unit tests for axm_ast.core.context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.core.context import detect_axm_tools, detect_stack, format_context_text


def _make_pyproject(path: Path, deps: list[str], *, build: str = "hatchling") -> None:
    """Write a minimal pyproject.toml."""
    dep_lines = ", ".join(f'"{d}"' for d in deps)
    (path / "pyproject.toml").write_text(
        f"[project]\n"
        f'name = "testpkg"\n'
        f"dependencies = [{dep_lines}]\n"
        f"[build-system]\n"
        f'requires = ["{build}"]\n'
        f'build-backend = "{build}.build"\n'
    )


class TestDetectStack:
    """Test pyproject.toml dependency categorization."""

    def test_detect_stack_cyclopts(self, tmp_path: Path) -> None:
        """Detects cyclopts as CLI framework."""
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        stack = detect_stack(tmp_path)
        assert "cli" in stack
        assert "cyclopts" in stack["cli"]

    def test_detect_stack_pydantic(self, tmp_path: Path) -> None:
        """Detects pydantic as models framework."""
        _make_pyproject(tmp_path, ["pydantic>=2.0"])
        stack = detect_stack(tmp_path)
        assert "models" in stack
        assert "pydantic" in stack["models"]

    def test_detect_stack_multiple(self, tmp_path: Path) -> None:
        """Categorizes all deps correctly."""
        _make_pyproject(
            tmp_path,
            ["cyclopts>=3.0", "pydantic>=2.0", "tree-sitter>=0.24"],
        )
        stack = detect_stack(tmp_path)
        assert "cyclopts" in stack["cli"]
        assert "pydantic" in stack["models"]
        assert "tree-sitter" in stack["parsing"]

    def test_detect_stack_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml → empty stack."""
        stack = detect_stack(tmp_path)
        assert stack == {}

    def test_detect_stack_unknown_deps(self, tmp_path: Path) -> None:
        """Unknown deps are not categorized."""
        _make_pyproject(tmp_path, ["obscure-lib>=1.0"])
        stack = detect_stack(tmp_path)
        # obscure-lib shouldn't appear in any category
        all_deps = [d for deps in stack.values() for d in deps]
        assert "obscure-lib" not in all_deps

    def test_detect_stack_dev_deps(self, tmp_path: Path) -> None:
        """Detects dev dependencies (pytest, ruff, mypy)."""
        _make_pyproject(tmp_path, [])
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        content += (
            '\n[dependency-groups]\ndev = ["pytest>=8.0", "ruff>=0.8", "mypy>=1.14"]\n'
        )
        pyproject.write_text(content)
        stack = detect_stack(tmp_path)
        assert "tests" in stack
        assert "lint" in stack
        assert "types" in stack

    def test_detect_stack_build_system(self, tmp_path: Path) -> None:
        """Detects build system from [build-system]."""
        _make_pyproject(tmp_path, [], build="hatchling")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack
        assert "hatchling" in stack["packaging"]

    def test_detect_stack_poetry(self, tmp_path: Path) -> None:
        """Detects poetry from build-system."""
        _make_pyproject(tmp_path, [], build="poetry.core.masonry.api")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack
        assert any("poetry" in d for d in stack["packaging"])


class TestDetectAxmTools:
    """Test AXM ecosystem tool detection."""

    def test_detect_axm_tools_available(self) -> None:
        """Finds installed AXM tools."""
        with patch("shutil.which", return_value="/usr/bin/axm-ast"):
            tools = detect_axm_tools()
        assert "axm-ast" in tools

    def test_detect_axm_tools_missing(self) -> None:
        """Missing tools are not included."""
        with patch("shutil.which", return_value=None):
            tools = detect_axm_tools()
        assert tools == {}

    def test_detect_axm_tools_partial(self) -> None:
        """Only installed tools are returned."""

        def _mock_which(name: str) -> str | None:
            return "/usr/bin/" + name if name == "axm-ast" else None

        with patch("shutil.which", side_effect=_mock_which):
            tools = detect_axm_tools()
        assert "axm-ast" in tools
        assert "axm-audit" not in tools


def _base(
    *, python: str | None = ">=3.12", stack: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "name": "my_pkg",
        "python": python,
        "stack": stack or {},
        "patterns": {
            "module_count": 10,
            "function_count": 25,
            "class_count": 5,
            "layout": "src",
        },
    }


@pytest.fixture()
def depth0_data() -> dict[str, Any]:
    d = _base()
    d["top_modules"] = [
        {"name": "core.engine", "symbol_count": 12, "stars": 4},
        {"name": "utils.helpers", "symbol_count": 8, "stars": 2},
    ]
    return d


@pytest.fixture()
def depth1_data() -> dict[str, Any]:
    d = _base(python=None)
    d["packages"] = [
        {"name": "core", "module_count": 4, "symbol_count": 15},
        {"name": "utils", "module_count": 3, "symbol_count": 10},
    ]
    return d


@pytest.fixture()
def depth2_data() -> dict[str, Any]:
    d = _base(python=None)
    d["packages"] = [
        {
            "name": "core",
            "module_count": 2,
            "symbol_count": 8,
            "modules": [
                {
                    "name": "core.engine",
                    "symbols": ["run", "stop", "init", "configure", "reset", "pause"],
                },
                {"name": "core.config", "symbols": ["load", "save"]},
            ],
        },
    ]
    return d


@pytest.fixture()
def data_with_stack() -> dict[str, Any]:
    d = _base(stack={"web": ["flask", "jinja2"], "data": ["pandas"]})
    d["top_modules"] = [
        {"name": "core.engine", "symbol_count": 12, "stars": 4},
    ]
    return d


@pytest.fixture()
def empty_package_data() -> dict[str, Any]:
    return {
        "name": "empty_pkg",
        "python": None,
        "stack": {},
        "patterns": {
            "module_count": 0,
            "function_count": 0,
            "class_count": 0,
            "layout": "flat",
        },
    }


def test_text_depth0_header(depth0_data: dict[str, Any]) -> None:
    text = format_context_text(depth0_data, depth=0)
    first_line = text.splitlines()[0]
    # Header: {name} | {layout} | {N} mod · {N} fn · {N} cls
    assert "my_pkg" in first_line
    assert "src" in first_line
    assert re.search(r"\d+ mod", first_line)
    assert re.search(r"\d+ fn", first_line)
    assert re.search(r"\d+ cls", first_line)
    assert "|" in first_line


def test_text_depth0_modules(depth0_data: dict[str, Any]) -> None:
    text = format_context_text(depth0_data, depth=0)
    assert "\u2605" in text  # ★
    assert "core.engine" in text
    assert "utils.helpers" in text


def test_text_depth1_packages(depth1_data: dict[str, Any]) -> None:
    text = format_context_text(depth1_data, depth=1)
    assert "Packages:" in text
    # Each package line has mod and sym counts
    assert "4 mod" in text
    assert "15 sym" in text
    assert "3 mod" in text
    assert "10 sym" in text


def test_text_depth2_symbols(depth2_data: dict[str, Any]) -> None:
    text = format_context_text(depth2_data, depth=2)
    # Symbol names appear in brackets
    assert "[" in text
    assert "run" in text
    assert "load" in text
    # 6 symbols in core.engine — truncation fires (limit is 5)
    assert "(+1)" in text


def test_text_includes_stack(data_with_stack: dict[str, Any]) -> None:
    text = format_context_text(data_with_stack, depth=0)
    assert "Stack:" in text
    assert "flask" in text


def test_text_includes_python(depth0_data: dict[str, Any]) -> None:
    text = format_context_text(depth0_data, depth=0)
    assert "python:" in text.lower()
    assert ">=3.12" in text


def test_text_omits_python_when_none(depth1_data: dict[str, Any]) -> None:
    # depth1_data has python=None
    text = format_context_text(depth1_data, depth=1)
    assert "python" not in text.lower()


def test_empty_package(empty_package_data: dict[str, Any]) -> None:
    text = format_context_text(empty_package_data, depth=0)
    # Should have header
    first_line = text.splitlines()[0]
    assert "empty_pkg" in first_line
    assert "0 mod" in first_line
    # No modules or packages section content beyond header
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Only header line(s), no module listing
    assert not any("\u2605" in line for line in lines)
