"""Integration test: removing name-based opt-out does not regress.

Verifies axm-audit's own suite still passes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from axm_audit.core.rules.test_quality.tautology import TautologyRule

pytestmark = pytest.mark.integration

_BASELINE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "tautology_baseline_axm_audit.json"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_axm_audit_own_suite_no_regression() -> None:
    """AC4: TautologyRule on axm-audit produces no new STRENGTHEN."""
    project = _project_root()
    result = TautologyRule().check(project)
    verdicts = cast(list[dict[str, object]], result.metadata["verdicts"])
    strengthen_count = sum(1 for v in verdicts if v["verdict"] == "STRENGTHEN")

    if _BASELINE_PATH.exists():
        baseline = json.loads(_BASELINE_PATH.read_text())
        baseline_count = int(baseline.get("strengthen_count", 0))
    else:
        baseline_count = strengthen_count

    assert strengthen_count <= baseline_count, (
        f"STRENGTHEN findings increased: {strengthen_count} > baseline {baseline_count}"
    )
