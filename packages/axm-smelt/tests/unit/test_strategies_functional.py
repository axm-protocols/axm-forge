from __future__ import annotations

import json

from axm_smelt.core.pipeline import check as _check
from axm_smelt.core.pipeline import smelt as _smelt


def _complex_json() -> str:
    """JSON blob that triggers all strategy types."""
    return json.dumps(
        {
            "wrapper": {
                "data": [
                    {"name": "Alice", "score": 3.14159, "notes": None},
                    {"name": "Bob", "score": 2.71828, "notes": ""},
                ]
            },
            "empty": {},
            "nested_single": {"inner": {"value": 1}},
        },
        indent=2,
    )


def test_aggressive_preset_all_strategies() -> None:
    result = _smelt(_complex_json(), preset="aggressive")
    assert result.savings_pct > 0
    assert len(result.strategies_applied) == 6


def test_check_strategy_estimates() -> None:
    data = json.dumps(
        {
            "a": {"b": 1},
            "c": None,
            "d": 3.14159,
        }
    )
    report = _check(data)
    assert hasattr(report, "strategy_estimates")
    assert isinstance(report.strategy_estimates, dict)
    # At least some strategies should show savings > 0
    positive = {k: v for k, v in report.strategy_estimates.items() if v > 0}
    assert len(positive) > 0


def test_moderate_preset_with_drop_nulls() -> None:
    data = json.dumps({"a": 1, "b": None, "c": "", "d": []})
    result = _smelt(data, preset="moderate")
    assert "drop_nulls" in result.strategies_applied
