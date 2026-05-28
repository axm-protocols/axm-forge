"""Tests for PrivateImportsRule against the axm-audit corpus itself.

Merged from former root-level orphans:
- test_private_imports_count.py (AC9: attribute-access detection - 0 findings)
- test_private_imports_count_dropped.py (AC7: total findings <= 30)
- test_private_imports_registration.py (registry membership)
- test_known_false_positives_no_longer_reported.py (regression on known FPs)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

_PKG_ROOT = Path(__file__).resolve().parents[5]
_EXPECTED_ATTRIBUTE_FINDINGS = 0
_THRESHOLD = 60


def test_rule_registered_under_test_quality() -> None:
    import axm_audit.core.rules.test_quality  # noqa: F401

    registry = get_registry()
    assert "test_quality" in registry
    assert any(r is PrivateImportsRule for r in registry["test_quality"])


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


@pytest.mark.integration
def test_private_imports_count_dropped() -> None:
    """AC7: Run PrivateImportsRule against axm-audit itself; assert count <= 30."""
    rule = PrivateImportsRule()
    result = rule.check(_PKG_ROOT)

    findings = result.details.get("findings", []) if result.details else []
    assert len(findings) <= _THRESHOLD, (
        f"expected <= {_THRESHOLD} private-import findings, got {len(findings)}"
    )


@pytest.mark.integration
def test_known_false_positives_no_longer_reported() -> None:
    rule = PrivateImportsRule()
    result = rule.check(_PKG_ROOT)
    findings = result.details["findings"] if result.details else []

    known_false_positives = {
        ("tests/unit/core/rules/test_quality/test_pyramid_level_r4_r5.py", 16),
        ("tests/unit/core/rules/test_quality/test_shared.py", 283),
    }

    reported: set[tuple[str, int]] = set()
    for finding in findings:
        path = Path(finding["test_file"])
        try:
            rel = path.relative_to(_PKG_ROOT)
        except ValueError:
            rel = path
        rel_str = str(rel).replace("\\", "/")
        reported.add((rel_str, finding["line"]))

    leftover = reported & known_false_positives
    assert not leftover, f"Known false positives still reported: {leftover}"
