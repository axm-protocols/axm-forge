"""Mis-tiered test — pure in-memory, belongs in tests/unit/."""

from __future__ import annotations

from relocate_only.core import add


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5
