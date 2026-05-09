"""AC7: TEST_QUALITY_PRIVATE_IMPORTS finding count drops below 30 after refactor."""

from __future__ import annotations

from pathlib import Path

import pytest

_AUDIT_PKG_ROOT = Path(__file__).resolve().parents[2]
_THRESHOLD = 30


@pytest.mark.integration
def test_private_imports_count_dropped() -> None:
    """Run PrivateImportsRule against axm-audit itself and assert count <= 30."""
    from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

    rule = PrivateImportsRule()
    result = rule.check(_AUDIT_PKG_ROOT)

    findings = result.details.get("findings", []) if result.details else []
    assert len(findings) <= _THRESHOLD, (
        f"expected <= {_THRESHOLD} private-import findings, got {len(findings)}"
    )
