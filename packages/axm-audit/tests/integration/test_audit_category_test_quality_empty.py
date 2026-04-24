"""Integration test: running audit with category='test_quality' on axm-audit itself."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project


@pytest.mark.integration
def test_audit_category_empty_rules_returns_valid_result() -> None:
    pkg_root = Path(__file__).resolve().parents[2]
    result = audit_project(pkg_root, category="test_quality")
    assert result is not None
    assert hasattr(result, "checks")
    assert isinstance(result.checks, list)
