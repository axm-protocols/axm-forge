"""Unit tests for axm_audit.core.fix.io_primitives — AC3."""

from __future__ import annotations

from pathlib import Path

import libcst as cst

from axm_audit.core.fix.io_primitives import (
    cst_load,
    cst_save,
)
from axm_audit.core.fix.io_primitives import cst_top_level as _top_level
from axm_audit.core.fix.io_primitives import cst_unwrap as _unwrap


def test_cst_load_save_roundtrip(tmp_path: Path) -> None:
    """AC3: cst_load and cst_save preserve source byte-for-byte."""
    src = "def f():\n    return 1\n"
    path = tmp_path / "mod.py"
    path.write_text(src)
    module = cst_load(path)
    assert module is not None
    out = tmp_path / "out.py"
    cst_save(out, module)
    assert out.read_text() == src


def test_top_level_returns_classdef_funcdef() -> None:
    """AC3: _top_level yields each top-level statement of a libcst Module."""
    src = "class C:\n    pass\n\ndef f():\n    pass\n\nx = 1\n"
    mod = cst.parse_module(src)
    assert _unwrap is not None
    nodes = list(_top_level(mod))
    assert len(nodes) == 3


def test_cst_load_returns_none_on_parse_error(tmp_path: Path) -> None:
    """AC3: cst_load returns None when libcst cannot parse the source."""
    path = tmp_path / "broken.py"
    path.write_text("def broken(\n")
    assert cst_load(path) is None


def test_unwrap_extracts_small_stmt_and_passes_through_compound() -> None:
    """AC3: _unwrap unwraps SimpleStatementLine; returns compound stmts as-is."""
    mod = cst.parse_module("import os\nclass C:\n    pass\n")
    simple, compound = mod.body[0], mod.body[1]
    assert isinstance(simple, cst.SimpleStatementLine)
    assert isinstance(_unwrap(simple), cst.Import)
    assert _unwrap(compound) is compound
