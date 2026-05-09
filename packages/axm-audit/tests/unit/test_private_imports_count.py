"""Integration test: AC9 — TEST_QUALITY_PRIVATE_IMPORTS count drops by
≥ 18 vs. post-T2 baseline once the auditor / security / quality / score /
coverage / hook tests no longer reach past public APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

_PKG_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_ATTRIBUTE_FINDINGS = 0


@pytest.mark.integration
def test_count_after_attribute_detection() -> None:
    """AC9: attribute-access detection.

    Corpus has been cleaned, expect 0 attribute findings.
    """
    result = PrivateImportsRule().check(_PKG_ROOT)
    findings = result.details.get("findings", []) if result.details else []
    attribute_findings = [f for f in findings if f.get("access_kind") == "attribute"]
    assert len(attribute_findings) == _EXPECTED_ATTRIBUTE_FINDINGS, (
        f"Expected {_EXPECTED_ATTRIBUTE_FINDINGS} attribute-access findings, "
        f"got {len(attribute_findings)}"
    )
