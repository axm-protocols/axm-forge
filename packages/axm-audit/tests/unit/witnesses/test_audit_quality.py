"""Unit tests for AuditQualityRule (no real I/O)."""

from __future__ import annotations

from axm_audit.witnesses.audit_quality import AuditQualityRule


class TestWorkingDirInvalid:
    """Edge case: working_dir does not exist."""

    def test_working_dir_invalid(self) -> None:
        rule = AuditQualityRule(
            categories=["lint"],
            working_dir="/nonexistent/path/xyz",
        )
        result = rule.validate("")

        assert result.passed is False
        assert result.feedback is not None
        assert "Not a directory" in result.feedback.why
