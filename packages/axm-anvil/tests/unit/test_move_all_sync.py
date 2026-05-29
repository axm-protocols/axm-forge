"""Unit tests for `__all__` synchronization on symbol move (AXM-1773, spec §5).

Covers AC1-AC5: when a moved symbol is in the source `__all__`, it is removed
from the source and appended to the target `__all__` — but only when each module
already declares `__all__`. Never synthesize a new `__all__`. Ordering and
formatting of untouched entries is preserved.
"""

from __future__ import annotations

from pathlib import Path

from axm_anvil.core.move import move_symbols


def _write(p: Path, text: str) -> Path:
    p.write_text(text)
    return p


def test_all_removed_from_source(tmp_path: Path) -> None:
    """AC1: a moved symbol present in source `__all__` is removed from it."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Foo", "Bar"]\n\n'
        "def Foo():\n    return 1\n\n"
        "def Bar():\n    return 2\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '"Foo"' not in plan.source_text_new
    assert '"Bar"' in plan.source_text_new


def test_all_added_to_existing_target(tmp_path: Path) -> None:
    """AC2: when target already declares `__all__`, the moved name is appended."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Foo"]\n\ndef Foo():\n    return 1\n',
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '"Foo"' in plan.target_text_new
    assert '"Baz"' in plan.target_text_new


def test_all_not_created_when_absent(tmp_path: Path) -> None:
    """AC3: no `__all__` is created on either side when absent."""
    src = _write(
        tmp_path / "src_mod.py",
        "def Foo():\n    return 1\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", "X = 1\n")
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert "__all__" not in plan.source_text_new
    assert "__all__" not in plan.target_text_new


def test_all_untouched_for_unexported_symbol(tmp_path: Path) -> None:
    """AC4: moving a symbol absent from source `__all__` leaves both untouched."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Bar"]\n\ndef Foo():\n    return 1\n\ndef Bar():\n    return 2\n',
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '__all__ = ["Bar"]' in plan.source_text_new
    assert '__all__ = ["Baz"]' in plan.target_text_new


def test_all_preserves_remaining_order(tmp_path: Path) -> None:
    """AC5: remaining `__all__` element order/formatting is preserved."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["A", "Foo", "B"]\n\n'
        "def A():\n    return 1\n\n"
        "def Foo():\n    return 2\n\n"
        "def B():\n    return 3\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Z"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '__all__ = ["A", "B"]' in plan.source_text_new
