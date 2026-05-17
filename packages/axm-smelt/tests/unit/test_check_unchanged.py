from __future__ import annotations

import pytest

from axm_smelt.core.pipeline import check
from tests.unit._helpers import _fixture_text

pytestmark = pytest.mark.integration


def test_check_unchanged() -> None:
    report = check(_fixture_text())
    assert isinstance(report.strategy_estimates, dict)
    assert report.strategy_estimates
