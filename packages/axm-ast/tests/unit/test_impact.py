from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_ast.core.impact import REEXPORT_WEIGHT, ImpactReport, score_impact


def test_score_impact_returns_high_above_threshold() -> None:
    report = ImpactReport(callers=[{}] * 5)
    assert score_impact(report) == "HIGH"


def test_score_impact_returns_low_below_medium() -> None:
    report = ImpactReport(callers=[{}] * 1)
    assert score_impact(report) == "LOW"


def test_score_impact_reexport_double_weight() -> None:
    one_reexport = ImpactReport(reexports=["some.module"])
    equivalent_callers = ImpactReport(callers=[{}] * REEXPORT_WEIGHT)
    assert score_impact(one_reexport) == score_impact(equivalent_callers)


def test_impact_report_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ImpactReport(unknown_field=[])  # type: ignore[call-arg]
