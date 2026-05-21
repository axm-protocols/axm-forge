"""Two distinct tuples: tests for beta() and gamma() — should split."""

from __future__ import annotations

from mixed.beta import beta
from mixed.gamma import gamma


def test_beta_returns_beta() -> None:
    assert beta() == "beta"


def test_gamma_returns_three() -> None:
    assert gamma() == 3
