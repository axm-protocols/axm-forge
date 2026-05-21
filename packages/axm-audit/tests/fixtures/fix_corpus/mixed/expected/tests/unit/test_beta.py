"""Canonical test_beta.py — merged from split (test_combined.py) + test_beta_extra.py."""

from __future__ import annotations

from mixed.beta import beta


def test_beta_returns_beta() -> None:
    assert beta() == "beta"


def test_beta_idempotent() -> None:
    assert beta() == beta()
