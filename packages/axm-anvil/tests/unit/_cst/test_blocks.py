from __future__ import annotations

import libcst as cst
import pytest

from axm_anvil._cst.blocks import extract_blocks


@pytest.mark.parametrize(
    ("source", "symbol"),
    [
        pytest.param(
            "class Foo:\n    pass\n\nclass Bar:\n    pass\n", "Foo", id="class"
        ),
        pytest.param("def f():\n    pass\n", "f", id="function"),
        pytest.param("CONST = 42\n", "CONST", id="assignment"),
    ],
)
def test_extract_blocks_single_symbol(source: str, symbol: str) -> None:
    tree = cst.parse_module(source)
    blocks = extract_blocks(tree, [symbol])
    assert len(blocks) == 1
    assert blocks[0].name == symbol


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
