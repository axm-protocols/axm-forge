from __future__ import annotations

import libcst as cst

from axm_anvil._cst.blocks import extract_blocks


def test_extract_blocks_class() -> None:
    tree = cst.parse_module("class Foo:\n    pass\n\nclass Bar:\n    pass\n")
    blocks = extract_blocks(tree, ["Foo"])
    assert len(blocks) == 1
    assert blocks[0].name == "Foo"


def test_extract_blocks_function() -> None:
    tree = cst.parse_module("def f():\n    pass\n")
    blocks = extract_blocks(tree, ["f"])
    assert len(blocks) == 1
    assert blocks[0].name == "f"


def test_extract_blocks_assignment() -> None:
    tree = cst.parse_module("CONST = 42\n")
    blocks = extract_blocks(tree, ["CONST"])
    assert len(blocks) == 1
    assert blocks[0].name == "CONST"


def test_extract_blocks_missing_symbol() -> None:
    tree = cst.parse_module("x = 1\n")
    blocks = extract_blocks(tree, ["Foo"])
    assert blocks == []


def test_extract_blocks_leading_comment() -> None:
    source = "# \u2500\u2500\u2500 Helpers \u2500\u2500\u2500\n\ndef f():\n    pass\n"
    tree = cst.parse_module(source)
    blocks = extract_blocks(tree, ["f"])
    assert len(blocks) == 1
    assert blocks[0].leading_lines
    comments = [
        line.comment.value
        for line in blocks[0].leading_lines
        if line.comment is not None
    ]
    assert any("Helpers" in c for c in comments)


def test_extract_blocks_excludes_self_reference() -> None:
    source = "class Foo:\n    def m(self):\n        Foo.x\n"
    tree = cst.parse_module(source)
    blocks = extract_blocks(tree, ["Foo"])
    assert len(blocks) == 1
    assert "Foo" not in blocks[0].referenced_names
