"""Unit test: PrivateImportsRule registered under test_quality category (no I/O)."""

from __future__ import annotations

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

__all__: list[str] = []


def test_rule_registered_under_test_quality() -> None:
    import axm_audit.core.rules.test_quality  # noqa: F401

    registry = get_registry()
    assert "test_quality" in registry
    assert any(r is PrivateImportsRule for r in registry["test_quality"])
