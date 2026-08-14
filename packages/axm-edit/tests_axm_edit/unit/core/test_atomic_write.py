"""Unit tests for the pure naming helper of the atomic-write primitive."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.atomic_write import temp_sibling_name


def test_temp_sibling_name_is_hidden_and_suffixed() -> None:
    """AC1: the temp name is a hidden dotfile ending in .axmtmp carrying the stem."""
    name = temp_sibling_name(Path("/x/mod.py"))

    assert name.startswith(".")
    assert name.endswith(".axmtmp")
    assert "mod" in name


def test_temp_sibling_name_never_collides_with_the_target() -> None:
    """AC1: the temp name is never equal to the target's own file name."""
    target = Path("/x/mod.py")

    name = temp_sibling_name(target)

    assert name != target.name
