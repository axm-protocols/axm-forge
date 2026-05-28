from __future__ import annotations

import libcst as cst

from axm_anvil._cst.transformers import RemoveSymbols


def test_remove_symbols_removes_class() -> None:
    source = "class A:\n    pass\n\nclass B:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"A"}))
    code = new.code
    assert "class A" not in code
    assert "class B" in code


def test_remove_symbols_preserves_formatting() -> None:
    source = "class A:\n    pass\n\n# section comment\n\nclass B:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"A"}))
    assert "class B:\n    pass" in new.code
    assert "# section comment" in new.code


def test_remove_symbols_skips_non_target() -> None:
    source = "class A:\n    pass\n"
    tree = cst.parse_module(source)
    new = tree.visit(RemoveSymbols({"X"}))
    assert new.code == source
