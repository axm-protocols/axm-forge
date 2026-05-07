from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_audit_finds_no_private_cross_module_imports_in_axm_ast():
    audit_mod = pytest.importorskip("axm_audit")

    runner = getattr(audit_mod, "run_audit", None) or getattr(audit_mod, "audit", None)
    if runner is None:
        pytest.skip("axm_audit runner entry point not available")

    try:
        result = runner(path=str(PACKAGE_ROOT), category="architecture")
    except TypeError:
        result = runner(str(PACKAGE_ROOT), "architecture")

    findings = getattr(result, "findings", None) or getattr(result, "data", result)
    text = repr(findings)

    assert "TEST_PRIVATE_IMPORT" not in text, (
        f"axm-ast still has TEST_PRIVATE_IMPORT findings: {text}"
    )
