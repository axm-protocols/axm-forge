"""Unit tests for the :class:`MoveContext` parameter bundle."""

from __future__ import annotations

import dataclasses

import pytest

from axm_anvil.core.context import MoveContext


def test_move_context_holds_grouped_parameters() -> None:
    """MoveContext round-trips the grouped move-plan parameters."""
    ctx = MoveContext(
        source_text_new="src-new",
        target_text_new="tgt-new",
        moved_names=["foo", "bar"],
        imports_added=["import os"],
        constants_added=["X = 1"],
        shared_map={},
    )

    assert ctx.source_text_new == "src-new"
    assert ctx.target_text_new == "tgt-new"
    assert ctx.moved_names == ["foo", "bar"]
    assert ctx.imports_added == ["import os"]
    assert ctx.constants_added == ["X = 1"]
    assert ctx.shared_map == {}
    # Optional caller/warning payloads default to ``None``.
    assert ctx.callers_updated is None
    assert ctx.redundant_import_warnings is None


def test_move_context_is_frozen() -> None:
    """MoveContext is immutable — assigning a field raises."""
    ctx = MoveContext(
        source_text_new="s",
        target_text_new="t",
        moved_names=[],
        imports_added=[],
        constants_added=[],
        shared_map={},
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.source_text_new = "mutated"  # type: ignore[misc]
