from __future__ import annotations

from axm_smelt.core.counter import count


def test_count_basic() -> None:
    result = count("hello world")
    assert isinstance(result, int)
    assert result > 0


def test_count_empty() -> None:
    result = count("")
    assert isinstance(result, int)
    assert result >= 0
