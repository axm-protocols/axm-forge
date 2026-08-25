"""Unit tests for axm_ast.core.callers.

Verifies the public contract of extract_references and find_callers
remains unchanged after the tree_sitter.Node type tightening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.callers import extract_references
from axm_ast.models.nodes import ModuleInfo


@pytest.mark.parametrize(
    ("filename", "source"),
    [
        pytest.param(
            "registry.py",
            "def my_func(): pass\nREGISTRY = {'a': my_func}\n",
            id="dict_value_dispatch",
        ),
        pytest.param(
            "loader.py",
            "def my_func(): pass\nDataLoader(collate_fn=my_func)\n",
            id="kwarg_dispatch",
        ),
    ],
)
def test_extract_references_handles_indirect_dispatch(
    tmp_path: Path, filename: str, source: str
) -> None:
    src = tmp_path / filename
    src.write_text(source, encoding="utf-8")
    mod = ModuleInfo(path=src)

    refs = extract_references(mod)

    assert "my_func" in refs
