from __future__ import annotations

import libcst as cst

from axm_anvil._cst.overloads import _detect_overload_group


def test_detect_overload_group_no_overloads() -> None:
    tree = cst.parse_module("def f():\n    pass\n")
    assert _detect_overload_group(tree, "f") == []


def test_detect_overload_group_full() -> None:
    source = (
        "from typing import overload\n"
        "@overload\n"
        "def process(x: int) -> int: ...\n"
        "@overload\n"
        "def process(x: str) -> str: ...\n"
        "def process(x):\n    return x\n"
    )
    tree = cst.parse_module(source)
    result = _detect_overload_group(tree, "process")
    assert len(result) == 3
    assert all(isinstance(node, cst.FunctionDef) for node in result)
    assert all(node.name.value == "process" for node in result)


def test_detect_overload_group_typing_prefix() -> None:
    source = (
        "import typing\n@typing.overload\ndef f(x: int): ...\ndef f(x):\n    return x\n"
    )
    tree = cst.parse_module(source)
    result = _detect_overload_group(tree, "f")
    assert len(result) == 2


def test_detect_overload_group_alias() -> None:
    source = (
        "from typing import overload as _ov\n"
        "@_ov\n"
        "def f(x: int): ...\n"
        "def f(x):\n    return x\n"
    )
    tree = cst.parse_module(source)
    result = _detect_overload_group(tree, "f")
    assert len(result) == 2


def test_detect_overload_group_unrelated_same_name() -> None:
    tree = cst.parse_module("def f():\n    pass\n")
    assert _detect_overload_group(tree, "f") == []
