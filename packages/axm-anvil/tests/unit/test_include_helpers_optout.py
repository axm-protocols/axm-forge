"""Unit tests for the ``include_helpers`` opt-out on ``move_symbols``."""

from __future__ import annotations

from pathlib import Path

from axm_anvil.core.move import move_symbols

_SOURCE = """\
from __future__ import annotations


def _helper(x: int) -> int:
    return x + 1


def public_fn(y: int) -> int:
    return _helper(y) * 2
"""

_TARGET = """\
from __future__ import annotations
"""


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src_mod.py"
    tgt = tmp_path / "tgt_mod.py"
    src.write_text(_SOURCE)
    tgt.write_text(_TARGET)
    return src, tgt


def test_include_helpers_true_copies_helper(tmp_path: Path) -> None:
    """AC1: default ``include_helpers=True`` copies referenced local helper."""
    src, tgt = _setup(tmp_path)
    plan = move_symbols(src, tgt, ["public_fn"], dry_run=True, include_helpers=True)
    assert "def _helper" in plan.target_text_new


def test_include_helpers_false_skips_and_warns(tmp_path: Path) -> None:
    """AC2,AC3: ``include_helpers=False`` skips helper and warns by name."""
    src, tgt = _setup(tmp_path)
    plan = move_symbols(src, tgt, ["public_fn"], dry_run=True, include_helpers=False)
    assert "def _helper" not in plan.target_text_new
    assert any("_helper" in w for w in plan.warnings)
