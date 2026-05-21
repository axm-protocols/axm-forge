"""Mis-tiered: pure in-memory test for alpha — should relocate to tests/unit/."""

from __future__ import annotations

from mixed.alpha import alpha


def test_alpha_returns_alpha() -> None:
    assert alpha() == "alpha"
