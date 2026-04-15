"""Tests for core auditor functionality."""

from pathlib import Path

import pytest


class TestAuditProjectFunction:
    """Test the main audit_project() function in axm-audit."""

    def test_audit_project_exists(self):
        """Test that audit_project can be imported from axm_audit."""
        from axm_audit import audit_project

        assert callable(audit_project)

    def test_audit_project_signature(self):
        """Test that audit_project has the correct signature."""
        import inspect

        from axm_audit import audit_project

        sig = inspect.signature(audit_project)
        params = list(sig.parameters.keys())

        assert "project_path" in params
        assert "category" in params
        assert "quick" in params

    def test_audit_project_returns_audit_result(self, tmp_path):
        """Test that audit_project returns an AuditResult object."""
        from axm_audit import AuditResult, audit_project

        # Create minimal project structure
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path)
        assert isinstance(result, AuditResult)

    def test_audit_project_nonexistent_path_raises_error(self):
        """Test that audit_project raises FileNotFoundError for invalid path."""
        from axm_audit import audit_project

        with pytest.raises(FileNotFoundError):
            audit_project(Path("/nonexistent/path"))

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
        """Test that category filtering works for all valid categories."""
        from axm_audit import audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path, category=category)
        assert result is not None

    def test_audit_project_quick_mode(self, tmp_path):
        """Test that quick mode runs only lint and type checks."""
        from axm_audit import audit_project

        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()

        result = audit_project(tmp_path, quick=True)
        # Quick mode should run fewer checks
        assert result.total <= 2  # Only lint and type checks


class TestGetRulesForCategory:
    """Test the get_rules_for_category() function."""

    def test_get_rules_for_category_exists(self):
        """Test that get_rules_for_category can be imported."""
        from axm_audit import get_rules_for_category

        assert callable(get_rules_for_category)

    def test_get_rules_all_categories(self):
        """Test getting all rules (no category filter)."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)
        assert len(rules) == 24

    @pytest.mark.parametrize(
        "category,expected_min",
        [
            ("lint", 1),
            ("type", 1),
            ("complexity", 1),
            ("security", 1),
            ("deps", 1),
            ("testing", 1),
            ("architecture", 1),
            ("practices", 1),
            ("structure", 1),
            ("tooling", 1),
        ],
    )
    def test_get_rules_by_category(self, category, expected_min):
        """Test getting rules filtered by category."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(category)
        assert len(rules) >= expected_min

    def test_get_rules_quick_mode(self):
        """Test that quick mode returns only lint and type rules."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None, quick=True)
        assert len(rules) == 2  # Only lint and type

    def test_get_rules_invalid_category(self):
        """Test that invalid category raises ValueError."""
        from axm_audit import get_rules_for_category

        with pytest.raises(ValueError):
            get_rules_for_category("invalid")


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
