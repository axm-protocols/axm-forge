"""NAME_MISMATCH: tests gamma() but file is misnamed → RENAME to test_gamma.py."""

from __future__ import annotations

from mixed.gamma import gamma


def test_gamma_is_positive() -> None:
    assert gamma() > 0
