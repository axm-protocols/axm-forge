"""CC budgets for refactored test_quality helpers (AXM-1577).

Pins the post-refactor cyclomatic-complexity ceiling for the three symbols
ticket AXM-1577 reduces, plus a sweep that also covers any new helper
extracted alongside them. Reads source files from disk → integration tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from radon.complexity import cc_visit

_PKG_ROOT = Path(__file__).resolve().parents[5] / "src" / "axm_audit"
_SHARED = _PKG_ROOT / "core" / "rules" / "test_quality" / "_shared.py"
_TAUTOLOGY = _PKG_ROOT / "core" / "rules" / "test_quality" / "tautology.py"

_CC_BUDGET = 10


def _cc_for(path: Path, name: str) -> int:
    blocks = cc_visit(path.read_text(encoding="utf-8"))
    matches = [b for b in blocks if b.name == name]
    assert matches, f"{name} not found in {path}"
    return max(b.complexity for b in matches)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "func"),
    [
        (_SHARED, "is_import_smoke_test"),
        (_TAUTOLOGY, "_check_assert"),
        (_SHARED, "detect_real_io"),
    ],
    ids=["is_import_smoke_test", "_check_assert", "detect_real_io"],
)
def test_target_function_cc_within_budget(path: Path, func: str) -> None:
    assert _cc_for(path, func) <= _CC_BUDGET


@pytest.mark.integration
@pytest.mark.parametrize("path", [_SHARED, _TAUTOLOGY], ids=["_shared", "tautology"])
def test_extracted_helpers_within_budget(path: Path) -> None:
    blocks = cc_visit(path.read_text(encoding="utf-8"))
    offenders = {b.name: b.complexity for b in blocks if b.complexity > _CC_BUDGET}
    assert not offenders, f"functions over CC {_CC_BUDGET} in {path.name}: {offenders}"
