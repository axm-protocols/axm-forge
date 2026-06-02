"""Integration tests for patch_file_dunder_depth (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import patch_file_dunder_depth

pytestmark = pytest.mark.integration


def test_patch_file_dunder_depth_subscript_form(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("from pathlib import Path\nROOT = Path(__file__).parents[2]\n")
    msgs = patch_file_dunder_depth(f, depth_delta=1)
    assert "parents[3]" in f.read_text()
    assert any("parents[2] -> parents[3]" in m for m in msgs)


def test_patch_file_dunder_depth_chained_parent_form(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parent.parent.parent\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-1)
    text = f.read_text()
    assert text.count(".parent") == 2
    assert any(".parent x3 -> .parent x2" in m for m in msgs)


def test_patch_file_dunder_depth_refuses_subscript_non_positive(
    tmp_path: Path,
) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parents[1]\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-2)
    assert "parents[1]" in f.read_text()
    assert any("refusing to patch" in m and "N<=0" in m for m in msgs)


def test_patch_file_dunder_depth_refuses_chain_non_positive(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parent.parent\n")
    msgs = patch_file_dunder_depth(f, depth_delta=-3)
    assert f.read_text() == "ROOT = Path(__file__).parent.parent\n"
    assert any("refusing to patch" in m and ".parent" in m for m in msgs)


def test_patch_file_dunder_depth_zero_delta_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("ROOT = Path(__file__).parents[2]\n")
    assert patch_file_dunder_depth(f, depth_delta=0) == []
    assert "parents[2]" in f.read_text()


def test_patch_file_dunder_depth_missing_file_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "absent.py"
    assert patch_file_dunder_depth(f, depth_delta=1) == []
