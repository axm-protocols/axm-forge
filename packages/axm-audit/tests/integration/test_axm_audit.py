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
from radon.complexity import cc_visit

import axm_audit

PKG_ROOT = Path(__file__).resolve().parents[2]
PYRAMID_LEVEL = (
    PKG_ROOT
    / "src"
    / "axm_audit"
    / "core"
    / "rules"
    / "test_quality"
    / "pyramid_level.py"
)
FIXTURE_DIR = PKG_ROOT / "tests" / "fixtures"
ALL_BASELINE = FIXTURE_DIR / "axm_audit_all_baseline.json"

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
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        ALL_BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        pytest.skip("baseline captured; rerun to validate")
    baseline = json.loads(ALL_BASELINE.read_text(encoding="utf-8"))
    assert current == baseline, "axm_audit.__all__ changed by refactor"


_CC_BUDGET = 10

_PKG_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _PKG_ROOT / "tests" / "fixtures"
_ALL_BASELINE = _FIXTURE_DIR / "axm_audit_all_baseline.json"
_SRC = (
    _PKG_ROOT
    / "src"
    / "axm_audit"
    / "core"
    / "rules"
    / "test_quality"
    / "tautology_triage.py"
)


def _cc_by_name() -> dict[str, int]:
    blocks = cc_visit(_SRC.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for block in blocks:
        out[block.fullname] = block.complexity
    return out


def test_classify_uniqueness_cc_within_budget() -> None:
    cc = _cc_by_name()
    assert "_classify_uniqueness" in cc, (
        "_classify_uniqueness not found in tautology_triage.py"
    )
    assert cc["_classify_uniqueness"] <= _CC_BUDGET, (
        f"_classify_uniqueness CC={cc['_classify_uniqueness']} "
        f"exceeds budget {_CC_BUDGET}"
    )


def test_extracted_helpers_within_budget__from_tautology_triage_complexity() -> None:
    cc = _cc_by_name()
    over = {name: c for name, c in cc.items() if c > _CC_BUDGET}
    assert over == {}, f"functions exceeding CC budget {_CC_BUDGET}: {over}"


def test_package_root_all_unchanged__from_tautology_triage_complexity() -> None:
    current = sorted(axm_audit.__all__)
    if not _ALL_BASELINE.exists():
        _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        _ALL_BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    baseline = sorted(json.loads(_ALL_BASELINE.read_text(encoding="utf-8")))
    assert current == baseline, (
        f"axm_audit.__all__ changed.\n"
        f"added: {sorted(set(current) - set(baseline))}\n"
        f"removed: {sorted(set(baseline) - set(current))}"
    )
