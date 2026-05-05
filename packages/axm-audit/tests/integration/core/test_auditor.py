"""Integration tests for auditor (real I/O)."""

from __future__ import annotations

import pytest


class TestAuditProjectFunctionIO:
    """Test the main audit_project() function in axm-audit (integration-level)."""

    def test_audit_project_returns_audit_result(self, tmp_path):
        """audit_project returns a populated AuditResult.

        Checks and a non-negative score must be present.
        """
        from axm_audit import AuditResult, audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path)
        assert isinstance(result, AuditResult)
        assert result.checks, "audit_project should produce at least one check"
        assert result.total == len(result.checks)

    def test_audit_project_invalid_category_raises_error(self, tmp_path):
        """Test that audit_project raises ValueError for invalid category."""
        from axm_audit import audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")

        with pytest.raises(ValueError, match="Invalid category"):
            audit_project(tmp_path, category="invalid_category")

    @pytest.mark.parametrize(
        "category",
        [
            "lint",
            "type",
            "complexity",
            "security",
            "deps",
            "testing",
            "architecture",
            "practices",
            "structure",
            "tooling",
        ],
    )
    def test_audit_project_category_filtering(self, tmp_path, category):
        """Category filter must restrict result.checks to the requested category."""
        from axm_audit import audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path, category=category)
        assert result.checks, f"category={category} produced no checks"
        leaked = {c.category or "" for c in result.checks}
        assert all(c.category == category for c in result.checks), (
            f"category={category} leaked checks: {sorted(leaked)}"
        )

    def test_audit_project_quick_mode(self, tmp_path):
        """Test that quick mode runs only lint and type checks."""
        from axm_audit import audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path, quick=True)
        # Quick mode should run fewer checks
        assert result.total <= 2  # Only lint and type checks


class TestAuditParallelExecution:
    """Tests for parallel rule execution and exception isolation."""

    def test_audit_uses_thread_pool(self, tmp_path, mocker):
        """Verify rules execute via ThreadPoolExecutor."""
        import concurrent.futures

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        spy = mocker.spy(concurrent.futures, "ThreadPoolExecutor")

        from axm_audit import audit_project

        audit_project(tmp_path, quick=True)
        spy.assert_called_once()

    def test_rule_exception_doesnt_crash_others(self, tmp_path, mocker):
        """One rule raising should not prevent others from completing."""
        from axm_audit.core.auditor import audit_project
        from axm_audit.core.rules.quality import LintingRule

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        # Make LintingRule crash
        mocker.patch.object(LintingRule, "check", side_effect=RuntimeError("boom"))

        result = audit_project(tmp_path, category="lint")
        # Other lint rules still ran (FormattingRule, DiffSizeRule, DeadCodeRule)
        assert result.total >= 2

        # The broken rule is marked as failed with crash message
        lint_checks = [c for c in result.checks if c.rule_id == "QUALITY_LINT"]
        assert len(lint_checks) == 1
        assert not lint_checks[0].passed
        assert "crashed" in lint_checks[0].message.lower()

        # Traceback enrichment (AXM-198)
        details = lint_checks[0].details
        assert details is not None
        assert "traceback" in details
        assert "boom" in details["traceback"]

    def test_traceback_truncated_500(self, tmp_path, mocker):
        """Traceback in details is truncated to last 500 characters."""
        from axm_audit.core.auditor import audit_project
        from axm_audit.core.rules.quality import LintingRule

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        # Make LintingRule crash with a very long exception message
        long_msg = "x" * 1000
        mocker.patch.object(LintingRule, "check", side_effect=RuntimeError(long_msg))

        result = audit_project(tmp_path, category="lint")
        lint_checks = [c for c in result.checks if c.rule_id == "QUALITY_LINT"]
        assert len(lint_checks) == 1
        details = lint_checks[0].details
        assert details is not None
        assert len(details["traceback"]) <= 500
