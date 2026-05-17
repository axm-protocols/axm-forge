"""Split from ``test_tools_impact.py``."""

import pytest
from pydantic import ValidationError

from axm_ast.core.impact import ImpactReport


def test_impact_report_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ImpactReport(unknown_field=[])  # type: ignore[call-arg]
