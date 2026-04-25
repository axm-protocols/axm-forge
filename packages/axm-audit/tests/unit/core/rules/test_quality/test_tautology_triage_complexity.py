from __future__ import annotations

import json
from pathlib import Path

from radon.complexity import cc_visit

import axm_audit

_PKG_ROOT = Path(__file__).resolve().parents[5]
_SRC = (
    _PKG_ROOT
    / "src"
    / "axm_audit"
    / "core"
    / "rules"
    / "test_quality"
    / "tautology_triage.py"
)
_FIXTURE_DIR = _PKG_ROOT / "tests" / "fixtures"
_ALL_BASELINE = _FIXTURE_DIR / "axm_audit_all_baseline.json"

_CC_BUDGET = 10


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


def test_extracted_helpers_within_budget() -> None:
    cc = _cc_by_name()
    over = {name: c for name, c in cc.items() if c > _CC_BUDGET}
    assert over == {}, f"functions exceeding CC budget {_CC_BUDGET}: {over}"


def test_package_root_all_unchanged() -> None:
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
