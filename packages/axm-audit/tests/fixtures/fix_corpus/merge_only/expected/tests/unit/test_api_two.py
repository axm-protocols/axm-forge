"""Second file targeting src/merge_only/api.py — canonical name is test_api.py (collides)."""

from __future__ import annotations

from merge_only.api import compute


def test_compute_handles_zero() -> None:
    assert compute(0) == 0
