from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltReport
from axm_smelt.strategies.base import SmeltStrategy


def test_smelt_report_fields() -> None:
    report = SmeltReport(
        original="hello world",
        compacted="hello world",
        original_tokens=10,
        compacted_tokens=8,
        savings_pct=20.0,
        format=Format.TEXT,
        strategies_applied=["minify"],
    )
    assert report.original == "hello world"
    assert report.compacted == "hello world"
    assert report.original_tokens == 10
    assert report.compacted_tokens == 8
    assert report.savings_pct == 20.0
    assert report.format == Format.TEXT
    assert report.strategies_applied == ["minify"]


def test_strategy_abc() -> None:
    with pytest.raises(TypeError):

        class Incomplete(SmeltStrategy):
            pass

        Incomplete()  # type: ignore[abstract]
