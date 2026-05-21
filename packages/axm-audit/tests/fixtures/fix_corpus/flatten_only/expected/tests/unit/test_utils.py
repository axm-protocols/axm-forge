"""Flattened test file — methods extracted from heterogeneous TestHeterogeneous class."""

from __future__ import annotations

from flatten_only.utils import normalize, trim


def test_trim_strips_whitespace() -> None:
    assert trim("  hi  ") == "hi"


def test_normalize_lowercases_and_strips() -> None:
    assert normalize("  Hi  ") == "hi"
