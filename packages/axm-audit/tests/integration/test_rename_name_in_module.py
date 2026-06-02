"""Integration tests for rename_name_in_module (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import rename_name_in_module

pytestmark = pytest.mark.integration


def test_rename_name_in_module_rewrites_defs_refs_and_strings(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text(
        '@pytest.mark.usefixtures("old_h")\n'
        "def test_a():\n"
        "    return old_h\n\n"
        "def old_h():\n"
        "    return 1\n"
    )
    rename_name_in_module(f, {"old_h": "new_h"})
    text = f.read_text()
    assert "def new_h(" in text
    assert "return new_h" in text
    assert '"new_h"' in text
    assert "old_h" not in text


def test_rename_name_in_module_renames_classdef(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("class OldHelper:\n    pass\n\nx = OldHelper\n")
    rename_name_in_module(f, {"OldHelper": "NewHelper"})
    text = f.read_text()
    assert "class NewHelper:" in text
    assert "x = NewHelper" in text


def test_rename_name_in_module_empty_mapping_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = "def f():\n    pass\n"
    f.write_text(original)
    rename_name_in_module(f, {})
    assert f.read_text() == original
