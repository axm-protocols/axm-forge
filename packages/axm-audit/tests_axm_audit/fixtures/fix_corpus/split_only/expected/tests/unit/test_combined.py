"""Two-tuple file: contains tests for both foo.py and bar.py.

axm-audit fix should split this into test_foo.py and test_bar.py.
"""

from __future__ import annotations

from split_only.bar import bar_value
from split_only.foo import foo_value


def test_foo_value() -> None:
    assert foo_value() == 1


def test_bar_value() -> None:
    assert bar_value() == 2
