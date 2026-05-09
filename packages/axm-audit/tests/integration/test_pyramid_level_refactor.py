"""Refactor regression tests for ``scan_test_file`` (AXM-1570).

These tests verify that:

* ``scan_test_file`` cyclomatic complexity is within the project budget.
* Every helper in ``pyramid_level.py`` is also within budget.
* The public surface of ``axm_audit`` is unchanged by the refactor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

PKG_ROOT = Path(__file__).resolve().parents[5]
PYRAMID_LEVEL = (
    PKG_ROOT
    / "src"
    / "axm_audit"
    / "core"
    / "rules"
    / "test_quality"
    / "pyramid_level.py"
)
BASELINE_DIR = Path(__file__).parent / "_baselines"
ALL_BASELINE = BASELINE_DIR / "axm_audit_all.json"

CC_BUDGET = 10


def _cc_blocks() -> list[Any]:
    from radon.complexity import cc_visit

    return list(cc_visit(PYRAMID_LEVEL.read_text(encoding="utf-8")))


def test_scan_test_file_cc_within_budget() -> None:
    """AC1 — ``scan_test_file`` cyclomatic complexity ≤ 10."""
    blocks = _cc_blocks()
    target = next((b for b in blocks if b.name == "scan_test_file"), None)
    assert target is not None, "scan_test_file not found in pyramid_level.py"
    assert target.complexity <= CC_BUDGET, (
        f"scan_test_file CC={target.complexity} (budget={CC_BUDGET})"
    )


def test_extracted_helpers_within_budget() -> None:
    """AC3 — every function in ``pyramid_level.py`` is within budget."""
    over_budget = [
        (b.name, b.complexity)
        for b in _cc_blocks()
        if b.name != "scan_test_file" and b.complexity > CC_BUDGET
    ]
    assert not over_budget, f"helpers exceeding CC budget ({CC_BUDGET}): {over_budget}"


def test_package_root_all_unchanged() -> None:
    """AC4 — ``axm_audit.__all__`` is unchanged by the refactor.

    The first invocation captures the current ``__all__`` as the baseline
    fixture and skips. Subsequent runs assert equality against the snapshot.
    """
    import axm_audit

    current = sorted(axm_audit.__all__)
    if not ALL_BASELINE.exists():
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        ALL_BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        pytest.skip("baseline captured; rerun to validate")
    baseline = json.loads(ALL_BASELINE.read_text(encoding="utf-8"))
    assert current == baseline, "axm_audit.__all__ changed by refactor"
