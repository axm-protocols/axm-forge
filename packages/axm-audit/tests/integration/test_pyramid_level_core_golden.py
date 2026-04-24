"""Golden test for PyramidLevelRule against the axm-audit core (R4/R5 disabled)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule

WORKSPACE = Path(
    "/Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge/packages/axm-audit"
)
BASELINE = Path(__file__).parent.parent / "fixtures" / "pyramid_core_baseline.json"


@pytest.mark.integration
def test_axm_audit_core_only_matches_v6_with_r4_r5_disabled() -> None:
    if not WORKSPACE.exists():
        pytest.skip(f"workspace not available: {WORKSPACE}")
    if not BASELINE.exists():
        pytest.skip(f"baseline not committed yet: {BASELINE}")

    rule = PyramidLevelRule()
    result = rule.check(WORKSPACE)

    actual = {
        "findings": sorted(
            (
                {
                    "path": str(Path(f.path).relative_to(WORKSPACE)),
                    "level": f.level,
                    "io_signals": sorted(f.io_signals),
                    "reason": f.reason,
                }
                for f in result.findings
            ),
            key=lambda d: (d["path"], d.get("reason", "")),
        )
    }
    expected = json.loads(BASELINE.read_text())
    assert actual == expected
