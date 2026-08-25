"""Unit tests for the language-dispatching extract layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.extract import extract_module, parse_path


def test_parse_path_python(tmp_path: Path) -> None:
    """A .py path parses through the Python backend."""
    src = tmp_path / "m.py"
    src.write_text("x = 1\n")
    tree = parse_path(src)
    assert tree.root_node.type == "module"


def test_extract_module_python(tmp_path: Path) -> None:
    """A .py path extracts a ModuleInfo with its symbols."""
    src = tmp_path / "m.py"
    src.write_text("def foo():\n    pass\n")
    mod = extract_module(src)
    assert [f.name for f in mod.functions] == ["foo"]


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
    """An unsupported extension raises ValueError, not a silent empty result."""
    src = tmp_path / "m.rs"
    src.write_text("fn main() {}")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_module(src)


def test_extract_module_typescript(tmp_path: Path) -> None:
    """A .ts path extracts through the TypeScript backend (if installed)."""
    pytest.importorskip("tree_sitter_typescript")
    src = tmp_path / "m.ts"
    src.write_text("export function f(): void {}\n")
    mod = extract_module(src)
    assert [fn.name for fn in mod.functions] == ["f"]
