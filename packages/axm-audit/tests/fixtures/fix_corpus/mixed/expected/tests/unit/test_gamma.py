"""Canonical test_gamma.py — merged from split (test_combined.py) + renamed (test_misnamed.py)."""

from __future__ import annotations

from mixed.gamma import gamma


def test_gamma_returns_three() -> None:
    assert gamma() == 3


def test_gamma_is_positive() -> None:
    assert gamma() > 0
