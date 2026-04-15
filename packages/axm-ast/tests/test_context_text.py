from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from axm_ast.core.context import format_context_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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
    # 6 symbols in core.engine — check truncation marker
    assert "(+" in text or all(
        s in text for s in ["run", "stop", "init", "configure", "reset", "pause"]
    )


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


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_tool_returns_text_and_data() -> None:
    from axm_ast.tools.context import ContextTool

    tool = ContextTool()
    result = tool.execute(
        path=str(Path(__file__).resolve().parent.parent),
        depth=1,
    )
    assert result.success
    assert isinstance(result.data, dict)
    assert isinstance(result.text, str)
    assert len(result.text) > 0
    assert len(result.data) > 0


def test_text_token_count_lower() -> None:
    from axm_ast.tools.context import ContextTool

    tool = ContextTool()
    result = tool.execute(
        path=str(Path(__file__).resolve().parent.parent),
        depth=1,
    )
    assert result.success
    json_str = json.dumps(result.data)
    # Approximate token count via whitespace split
    assert result.text is not None
    text_tokens = len(result.text.split())
    json_tokens = len(json_str.split())
    assert text_tokens < json_tokens


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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


def test_workspace() -> None:
    from axm_ast.tools.context import ContextTool

    # axm-forge workspace root
    ws_path = Path(__file__).resolve().parent.parent.parent.parent
    tool = ContextTool()
    result = tool.execute(path=str(ws_path), depth=1)
    if not result.success:
        pytest.skip("workspace detection not available in test environment")
    assert isinstance(result.text, str)
    assert len(result.text) > 0
    # workspace name should appear
    assert "axm" in result.text.lower()
