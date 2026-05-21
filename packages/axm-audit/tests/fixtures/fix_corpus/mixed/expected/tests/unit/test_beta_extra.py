"""Second file targeting beta() — collides with split output on canonical name → MERGE."""

from __future__ import annotations

from mixed.beta import beta


def test_beta_idempotent() -> None:
    assert beta() == beta()
