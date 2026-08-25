"""First file targeting src/merge_only/api.py — canonical name is test_api.py."""

from __future__ import annotations

from merge_only.api import compute


def test_compute_doubles_positive() -> None:
    assert compute(3) == 6
