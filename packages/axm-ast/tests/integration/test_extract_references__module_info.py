"""Unit tests for axm_ast.core.callers.

Verifies the public contract of extract_references and find_callers
remains unchanged after the tree_sitter.Node type tightening.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.callers import extract_references
from axm_ast.models.nodes import ModuleInfo


def test_extract_references_handles_dict_value_dispatch(tmp_path: Path) -> None:
    src = tmp_path / "registry.py"
    src.write_text("def my_func(): pass\nREGISTRY = {'a': my_func}\n", encoding="utf-8")
    mod = ModuleInfo(path=src)

    refs = extract_references(mod)

    assert "my_func" in refs


def test_extract_references_handles_kwarg_dispatch(tmp_path: Path) -> None:
    src = tmp_path / "loader.py"
    src.write_text(
        "def my_func(): pass\nDataLoader(collate_fn=my_func)\n",
        encoding="utf-8",
    )
    mod = ModuleInfo(path=src)

    refs = extract_references(mod)

    assert "my_func" in refs
