from __future__ import annotations

import pytest

from axm_smelt.core.pipeline import smelt
from tests.unit._helpers import _fixture_text

pytestmark = pytest.mark.integration


def test_pipeline_smelt_unchanged() -> None:
    text = _fixture_text()
    report = smelt(text)
    assert report.compacted_tokens <= report.original_tokens
    assert isinstance(report.strategies_applied, list)
    assert report.strategies_applied, "expected at least one strategy applied"
