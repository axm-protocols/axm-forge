"""Canonical test file for src/split_only/bar.py (split from test_combined.py)."""

from __future__ import annotations

from split_only.bar import bar_value


def test_bar_value() -> None:
    assert bar_value() == 2
