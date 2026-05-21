"""Merged canonical file (test_api_one.py + test_api_two.py)."""

from __future__ import annotations

from merge_only.api import compute


def test_compute_doubles_positive() -> None:
    assert compute(3) == 6


def test_compute_handles_zero() -> None:
    assert compute(0) == 0
