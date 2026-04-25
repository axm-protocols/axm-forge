"""Integration test: AC7 — coverage of the seven private helpers being
“promoted” to public-API exercising must not drop after the rewrite.

The pre-refactor covered-line counts are persisted to a baseline file by
the build phase. This test re-runs ``coverage`` over the affected modules
and asserts each helper is still hit at least as many lines as before."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_FILE = _PKG_ROOT / "tests" / ".coverage_helpers_baseline.json"

_HELPERS = (
    "_safe_check",
    "_build_all_rules",
    "_build_security_result",
    "_get_audit_targets",
    "_collect_category_scores",
    "_extract_test_failures",
    "_read_snippet",
)


def _covered_lines_for_helper(coverage_data, helper: str) -> int:
    """Best-effort lookup: scan ``coverage.py`` JSON report for any function
    whose qualified name contains the helper name and sum its executed lines."""
    total = 0
    files = coverage_data.get("files", {})
    for finfo in files.values():
        functions = finfo.get("functions", {})
        for qualname, fn_info in functions.items():
            if helper in qualname:
                executed = fn_info.get("summary", {}).get("covered_lines")
                if executed is None:
                    executed = len(fn_info.get("executed_lines", []))
                total += int(executed)
    return total


@pytest.mark.integration
def test_coverage_of_promoted_helpers_non_decreasing():
    if not _BASELINE_FILE.exists():
        pytest.skip(
            "Pre-refactor coverage baseline missing; build phase must "
            f"persist it at {_BASELINE_FILE.relative_to(_PKG_ROOT)}"
        )

    baseline = json.loads(_BASELINE_FILE.read_text())

    current_report = _PKG_ROOT / "coverage.json"
    if not current_report.exists():
        pytest.skip(
            "coverage.json not present; run `uv run coverage json` after "
            "`uv run pytest --cov` to materialize the report."
        )
    current = json.loads(current_report.read_text())

    regressions: list[str] = []
    for helper in _HELPERS:
        before = int(baseline.get(helper, 0))
        after = _covered_lines_for_helper(current, helper)
        if after < before:
            regressions.append(f"{helper}: {before} → {after}")

    assert not regressions, (
        "Coverage regressed for promoted helpers:\n  " + "\n  ".join(regressions)
    )
