from __future__ import annotations

import json

import pytest

from axm_smelt.core.pipeline import check

pytestmark = pytest.mark.integration


def _fixture_text() -> str:
    payload = {
        "users": [
            {"id": i, "name": f"user_{i}", "active": True, "notes": None}
            for i in range(20)
        ],
        "meta": {"version": 1, "description": "   spaced   text   "},
    }
    return json.dumps(payload, indent=2)


def test_check_unchanged() -> None:
    report = check(_fixture_text())
    assert isinstance(report.strategy_estimates, dict)
    assert report.strategy_estimates
