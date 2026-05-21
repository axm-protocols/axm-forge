"""Heterogeneous Test* class — methods cover unrelated SUTs and should be flattened."""

from __future__ import annotations

from flatten_only.utils import normalize, trim


class TestHeterogeneous:
    """Mixes assertions on trim() and normalize() — no shared state."""

    def test_trim_strips_whitespace(self) -> None:
        assert trim("  hi  ") == "hi"

    def test_normalize_lowercases_and_strips(self) -> None:
        assert normalize("  Hi  ") == "hi"
