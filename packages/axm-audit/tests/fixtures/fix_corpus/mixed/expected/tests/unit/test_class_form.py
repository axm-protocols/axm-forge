"""Heterogeneous Test* class — should FLATTEN (and rename canonical → test_alpha.py)."""

from __future__ import annotations

from mixed.alpha import alpha


class TestAlpha:
    """Class wrapper that should be flattened."""

    def test_alpha_is_string(self) -> None:
        assert isinstance(alpha(), str)
