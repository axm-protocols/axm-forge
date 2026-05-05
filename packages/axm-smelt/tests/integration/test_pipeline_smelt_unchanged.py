from __future__ import annotations

import json

import pytest

from axm_smelt.core.pipeline import smelt

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


def test_pipeline_smelt_unchanged() -> None:
    text = _fixture_text()
    report = smelt(text)
    assert report.compacted_tokens <= report.original_tokens
    assert isinstance(report.strategies_applied, list)
    assert report.strategies_applied, "expected at least one strategy applied"
