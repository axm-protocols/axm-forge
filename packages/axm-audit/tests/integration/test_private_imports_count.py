"""Integration test: AC9 — TEST_QUALITY_PRIVATE_IMPORTS count drops by
≥ 18 vs. post-T2 baseline once the auditor / security / quality / score /
coverage / hook tests no longer reach past public APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

_PKG_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_FILE = _PKG_ROOT / "tests" / ".private_imports_baseline"
_DROP_REQUIRED = 18


@pytest.mark.integration
def test_private_imports_count_dropped_further():
    if not _BASELINE_FILE.exists():
        pytest.skip(
            "Post-T2 baseline file missing; build phase must persist it at "
            f"{_BASELINE_FILE.relative_to(_PKG_ROOT)}"
        )

    baseline = int(_BASELINE_FILE.read_text().strip())

    result = PrivateImportsRule().check(_PKG_ROOT)

    details = result.details or {}
    total = details.get("total")
    if total is None:
        # Fallback: derive from violation list if present.
        violations = details.get("violations") or details.get("items") or []
        total = len(violations)

    assert total <= baseline - _DROP_REQUIRED, (
        f"Expected private-imports count ≤ {baseline - _DROP_REQUIRED} "
        f"(post-T2 baseline {baseline} - {_DROP_REQUIRED}), got {total}."
    )
