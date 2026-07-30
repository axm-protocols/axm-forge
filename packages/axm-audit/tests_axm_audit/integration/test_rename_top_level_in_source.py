"""Integration tests for rename_top_level_in_source (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import rename_top_level_in_source

pytestmark = pytest.mark.integration


def test_rename_top_level_in_source_renames_header_only(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def old_fn():\n    return old_fn\n")
    rename_top_level_in_source(f, {"old_fn": "new_fn"})
    text = f.read_text()
    # Only the def header is renamed; the inner reference is left untouched.
    assert "def new_fn(" in text
    assert "return old_fn" in text


def test_rename_top_level_in_source_empty_mapping_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = "def keep():\n    pass\n"
    f.write_text(original)
    rename_top_level_in_source(f, {})
    assert f.read_text() == original
