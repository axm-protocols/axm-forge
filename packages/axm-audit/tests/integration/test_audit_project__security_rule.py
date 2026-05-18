"""Public-API tests for ``audit_project`` (replaces private ``_safe_check`` /
``_build_all_rules`` direct calls in ``tests/core/rules/test_rules.py``)."""

from __future__ import annotations

from axm_audit import AuditResult, audit_project
from tests.integration._helpers import _make_minimal_project


def test_audit_project_safe_check_isolation(tmp_path, monkeypatch):
    """AC1: A rule that raises must not abort the audit; result records the failure."""
    _make_minimal_project(tmp_path)

    from axm_audit.core.rules.security import SecurityRule

    def boom(self, project_path):
        raise RuntimeError("rule exploded")

    monkeypatch.setattr(SecurityRule, "check", boom)

    result = audit_project(tmp_path)

    assert isinstance(result, AuditResult)
    failed = [c for c in result.checks if not c.passed]
    assert failed, "expected at least one failed check entry from the raising rule"
    assert any("security" in (c.rule_id or "").lower() for c in failed)
    # Other rules still produced entries
    assert len(result.checks) > 1
