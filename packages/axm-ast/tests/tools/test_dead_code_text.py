from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.tools.dead_code import DeadCodeTool


@pytest.fixture()
def tool() -> DeadCodeTool:
    return DeadCodeTool()


def _dead_symbol(name: str, module_path: str, line: int, kind: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, module_path=module_path, line=line, kind=kind)


# --- Unit tests ---


def test_text_rendering_empty(tool: DeadCodeTool, tmp_path: Any) -> None:
    """Clean package (all symbols in __all__) -> header-only text."""
    pkg_dir = tmp_path / "clean_pkg"
    pkg_dir.mkdir()

    mock_pkg = SimpleNamespace()

    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.dead_code.find_dead_code", return_value=[]),
    ):
        result = tool.execute(path=str(pkg_dir))

    assert result.success is True
    assert result.text == "ast_dead_code | 0 dead symbols"
    assert result.data["dead_symbols"] == []
    assert result.data["total"] == 0


def test_text_rendering_populated(tool: DeadCodeTool, tmp_path: Any) -> None:
    """Package with dead symbols -> header + symbol lines with relative paths."""
    pkg_dir = tmp_path / "dead_pkg"
    pkg_dir.mkdir()
    pkg_root = str(pkg_dir)

    dead_symbols = [
        _dead_symbol(
            name="unused_function",
            module_path=f"{pkg_root}/src/dead_pkg/utils.py",
            line=10,
            kind="function",
        ),
    ]

    mock_pkg = SimpleNamespace()

    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.dead_code.find_dead_code", return_value=dead_symbols),
    ):
        result = tool.execute(path=str(pkg_dir))

    assert result.success is True
    text = result.text
    assert text is not None
    # Header present
    assert "ast_dead_code | 1 dead symbols" in text
    # Abbreviated kind
    assert "func" in text
    # Symbol name
    assert "unused_function" in text
    # Relative path — no absolute prefix
    assert pkg_root not in text
    assert "src/dead_pkg/utils.py" in text
    # Data unchanged
    assert len(result.data["dead_symbols"]) == 1
    assert result.data["total"] == 1


# --- Edge cases ---


def test_unknown_kind_falls_back_to_raw() -> None:
    """Future kind not in _KIND_SHORT falls back to raw kind string."""
    symbols = [
        {
            "name": "MyProto",
            "module_path": "/pkg/src/proto.py",
            "line": 5,
            "kind": "protocol",
        },
    ]
    text = DeadCodeTool._render_text(symbols, pkg_root="/pkg")
    lines = text.split("\n")
    # Kind column should contain the raw 'protocol' string
    assert "protocol" in lines[-1]
    assert "MyProto" in lines[-1]


def test_path_outside_package_root_preserved() -> None:
    """module_path that doesn't start with pkg_root keeps full absolute path."""
    symbols = [
        {
            "name": "stray_func",
            "module_path": "/other/lib/mod.py",
            "line": 42,
            "kind": "function",
        },
    ]
    text = DeadCodeTool._render_text(symbols, pkg_root="/pkg")
    # Full absolute path preserved since it doesn't share the prefix
    assert "/other/lib/mod.py" in text
