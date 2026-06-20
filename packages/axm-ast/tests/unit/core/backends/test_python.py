"""Unit tests for the Python backend adapter."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.backends.python import PythonBackend


def test_suffixes_and_name() -> None:
    """The Python backend owns .py and is named python."""
    backend = PythonBackend()
    assert backend.suffixes == (".py",)
    assert backend.name == "python"


def test_extract_module_returns_symbols(tmp_path: Path) -> None:
    """extract_module returns the functions/classes of a real .py file."""
    src = tmp_path / "m.py"
    src.write_text("def foo():\n    pass\n\nclass Bar:\n    pass\n")
    mod = PythonBackend().extract_module(src)
    assert [f.name for f in mod.functions] == ["foo"]
    assert [c.name for c in mod.classes] == ["Bar"]


def test_parse_source_round_trips() -> None:
    """parse_source produces a tree-sitter module root."""
    tree = PythonBackend().parse_source("x = 1")
    assert tree.root_node.type == "module"
