"""Canonical-named test file for src/rename_only/widget.py."""

from __future__ import annotations

from rename_only.widget import make_widget


def test_make_widget_carries_label() -> None:
    assert make_widget("hello") == {"label": "hello"}
