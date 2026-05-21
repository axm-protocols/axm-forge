"""NAME_MISMATCH: test file targets src/rename_only/widget.py but is named test_wrong_name.py."""

from __future__ import annotations

from rename_only.widget import make_widget


def test_make_widget_carries_label() -> None:
    assert make_widget("hello") == {"label": "hello"}
