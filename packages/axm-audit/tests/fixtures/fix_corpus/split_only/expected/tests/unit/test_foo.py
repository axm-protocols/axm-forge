"""Canonical test file for src/split_only/foo.py (split from test_combined.py)."""

from __future__ import annotations

from split_only.foo import foo_value


def test_foo_value() -> None:
    assert foo_value() == 1
