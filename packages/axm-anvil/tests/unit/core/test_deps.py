from __future__ import annotations

import libcst as cst

from axm_anvil.core.deps import (
    gather_source_constants,
    gather_source_helpers,
    gather_source_imports,
    topo_sort_constants,
)


def _const_stmt(code: str) -> cst.SimpleStatementLine:
    tree = cst.parse_module(code)
    stmt = tree.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    return stmt


def _name_of(stmt: cst.SimpleStatementLine) -> str:
    node = stmt.body[0]
    if isinstance(node, cst.Assign):
        target = node.targets[0].target
    elif isinstance(node, cst.AnnAssign):
        target = node.target
    else:
        raise AssertionError(f"unexpected stmt: {type(node).__name__}")
    assert isinstance(target, cst.Name)
    return target.value


def test_gather_source_imports_stdlib() -> None:
    tree = cst.parse_module("from pathlib import Path\n")
    mapping = gather_source_imports(tree)
    assert "Path" in mapping
    info = mapping["Path"]
    assert info.module == "pathlib"
    assert info.obj == "Path"


def test_gather_source_imports_alias() -> None:
    tree = cst.parse_module("import numpy as np\n")
    mapping = gather_source_imports(tree)
    assert "np" in mapping
    info = mapping["np"]
    assert info.module == "numpy"
    assert info.alias == "np"


def test_gather_source_imports_relative() -> None:
    tree = cst.parse_module("from ..core import models\n")
    mapping = gather_source_imports(tree)
    assert "models" in mapping
    info = mapping["models"]
    assert info.relative == 2


def test_gather_source_constants_assign() -> None:
    tree = cst.parse_module("X = 42\n")
    mapping = gather_source_constants(tree)
    assert "X" in mapping


def test_gather_source_constants_annassign() -> None:
    tree = cst.parse_module("X: int = 42\n")
    mapping = gather_source_constants(tree)
    assert "X" in mapping


def test_gather_source_helpers() -> None:
    source = "def foo():\n    pass\n\ndef bar():\n    pass\n\nclass Baz:\n    pass\n"
    tree = cst.parse_module(source)
    helpers = gather_source_helpers(tree)
    assert set(helpers.keys()) == {"foo", "bar", "Baz"}


def test_gather_source_helpers_ignores_nested() -> None:
    source = "def outer():\n    def inner():\n        pass\n"
    tree = cst.parse_module(source)
    helpers = gather_source_helpers(tree)
    assert set(helpers.keys()) == {"outer"}


def test_topo_sort_linear() -> None:
    constants = {
        "A": _const_stmt("A = B + 1\n"),
        "B": _const_stmt("B = C + 1\n"),
        "C": _const_stmt("C = 1\n"),
    }
    ordered = topo_sort_constants(constants)
    names = [_name_of(s) for s in ordered]
    assert names.index("C") < names.index("B") < names.index("A")


def test_topo_sort_no_deps() -> None:
    constants = {
        "A": _const_stmt("A = 1\n"),
        "B": _const_stmt("B = 2\n"),
        "C": _const_stmt("C = 3\n"),
    }
    ordered = topo_sort_constants(constants)
    names = [_name_of(s) for s in ordered]
    assert set(names) == {"A", "B", "C"}
    assert len(names) == 3


def test_topo_sort_multiple_roots() -> None:
    constants = {
        "A": _const_stmt("A = C + 1\n"),
        "B": _const_stmt("B = C + 2\n"),
        "C": _const_stmt("C = 0\n"),
    }
    ordered = topo_sort_constants(constants)
    names = [_name_of(s) for s in ordered]
    c_idx = names.index("C")
    assert c_idx < names.index("A")
    assert c_idx < names.index("B")


def test_topo_sort_cycle_does_not_crash() -> None:
    constants = {
        "A": _const_stmt("A = B + 1\n"),
        "B": _const_stmt("B = A + 1\n"),
    }
    ordered = topo_sort_constants(constants)
    assert len(ordered) == 2
    names = {_name_of(s) for s in ordered}
    assert names == {"A", "B"}
