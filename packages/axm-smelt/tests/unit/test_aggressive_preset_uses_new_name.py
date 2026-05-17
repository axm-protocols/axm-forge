from __future__ import annotations

import json

import pytest

from axm_smelt.core.pipeline import smelt

pytestmark = pytest.mark.integration


def test_aggressive_preset_uses_new_name() -> None:
    payload = json.dumps(
        {
            "items": [
                {"label": "a-very-long-repeated-value-string-payload"},
                {"label": "a-very-long-repeated-value-string-payload"},
                {"label": "a-very-long-repeated-value-string-payload"},
            ]
        }
    )
    report = smelt(payload, preset="aggressive")
    applied = getattr(report, "strategies_applied", None) or getattr(
        report, "applied", []
    )
    assert "dedup_values" not in applied
