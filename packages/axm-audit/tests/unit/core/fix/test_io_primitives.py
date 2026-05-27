"""Unit tests for axm_audit.core.fix.io_primitives — AC3."""

from __future__ import annotations

import libcst as cst

from axm_audit.core.fix.io_primitives import cst_top_level as _top_level
from axm_audit.core.fix.io_primitives import cst_unwrap as _unwrap


def test_top_level_returns_classdef_funcdef() -> None:
    """AC3: _top_level yields each top-level statement of a libcst Module."""
    src = "class C:\n    pass\n\ndef f():\n    pass\n\nx = 1\n"
    mod = cst.parse_module(src)
    assert _unwrap is not None
    nodes = list(_top_level(mod))
    assert len(nodes) == 3


def test_unwrap_extracts_small_stmt_and_passes_through_compound() -> None:
    """AC3: _unwrap unwraps SimpleStatementLine; returns compound stmts as-is."""
    mod = cst.parse_module("import os\nclass C:\n    pass\n")
    simple, compound = mod.body[0], mod.body[1]
    assert isinstance(simple, cst.SimpleStatementLine)
    assert isinstance(_unwrap(simple), cst.Import)
    assert _unwrap(compound) is compound
