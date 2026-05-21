"""Canonical test_alpha.py — merged from relocated integration test + flattened class."""

from __future__ import annotations

from mixed.alpha import alpha


def test_alpha_returns_alpha() -> None:
    assert alpha() == "alpha"


def test_alpha_is_string() -> None:
    assert isinstance(alpha(), str)
