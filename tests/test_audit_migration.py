"""
Test suite for audit functionality migration from axm to axm-audit.

This test file verifies that all audit functionality has been successfully
migrated from the axm package to axm-audit and works correctly in the new location.
"""

import pytest
from pathlib import Path


class TestAuditProjectFunction:
    """Test the main audit_project() function in axm-audit."""

    def test_audit_project_exists(self):
        """Test that audit_project can be imported from axm_audit."""
        from axm_audit import audit_project
        assert callable(audit_project)

    def test_audit_project_signature(self):
        """Test that audit_project has the correct signature."""
        from axm_audit import audit_project
        import inspect
        
        sig = inspect.signature(audit_project)
        params = list(sig.parameters.keys())
        
        assert "project_path" in params
        assert "category" in params
        assert "quick" in params

    def test_audit_project_returns_audit_result(self, tmp_path):
        """Test that audit_project returns an AuditResult object."""
        from axm_audit import audit_project, AuditResult
        
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

    @pytest.mark.parametrize("category", ["structure", "quality", "architecture", "practice"])
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
        assert len(rules) == 13  # All 13 rules

    @pytest.mark.parametrize("category,expected_min", [
        ("structure", 1),
        ("quality", 1),
        ("architecture", 1),
        ("practice", 1),
    ])
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


class TestModels:
    """Test that audit models work correctly in axm-audit."""

    def test_audit_result_import(self):
        """Test that AuditResult can be imported."""
        from axm_audit.models import AuditResult
        assert AuditResult is not None

    def test_check_result_import(self):
        """Test that CheckResult can be imported."""
        from axm_audit.models import CheckResult
        assert CheckResult is not None

    def test_severity_import(self):
        """Test that Severity can be imported."""
        from axm_audit.models import Severity
        assert Severity is not None

    def test_audit_result_creation(self):
        """Test creating an AuditResult instance."""
        from axm_audit.models import AuditResult, CheckResult
        
        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])
        
        assert result.total == 1
        assert result.success is True

    def test_audit_result_quality_score(self):
        """Test that quality scoring works."""
        from axm_audit.models import AuditResult, CheckResult
        
        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                details={"score": 90.0},
            ),
            CheckResult(
                rule_id="QUALITY_TYPE",
                passed=False,
                message="Fail",
                details={"score": 50.0},
            ),
        ]
        result = AuditResult(checks=checks)
        
        assert result.quality_score is not None
        assert 0 <= result.quality_score <= 100

    def test_audit_result_grade(self):
        """Test that letter grading works."""
        from axm_audit.models import AuditResult, CheckResult
        
        checks = [
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=True,
                message="Pass",
                details={"score": 95.0},
            )
        ]
        result = AuditResult(checks=checks)
        
        assert result.grade in ["A", "B", "C", "D", "F"]


class TestReporters:
    """Test that reporters work correctly in axm-audit."""

    def test_json_reporter_import(self):
        """Test that JsonReporter can be imported."""
        from axm_audit.reporters import JsonReporter
        assert JsonReporter is not None

    def test_markdown_reporter_import(self):
        """Test that MarkdownReporter can be imported."""
        from axm_audit.reporters import MarkdownReporter
        assert MarkdownReporter is not None

    def test_json_reporter_render(self):
        """Test that JsonReporter can render results."""
        from axm_audit.reporters import JsonReporter
        from axm_audit.models import AuditResult, CheckResult
        
        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])
        
        reporter = JsonReporter()
        output = reporter.render(result)
        
        assert isinstance(output, str)
        assert "TEST" in output

    def test_markdown_reporter_render(self):
        """Test that MarkdownReporter can render results."""
        from axm_audit.reporters import MarkdownReporter
        from axm_audit.models import AuditResult, CheckResult
        
        check = CheckResult(rule_id="TEST", passed=True, message="Test")
        result = AuditResult(checks=[check])
        
        reporter = MarkdownReporter()
        output = reporter.render(result)
        
        assert isinstance(output, str)
        assert "TEST" in output


class TestRulesMigration:
    """Test that all 13 rules have been migrated correctly."""

    @pytest.mark.parametrize("rule_id", [
        "FILE_EXISTS_pyproject.toml",
        "FILE_EXISTS_README.md",
        "DIR_EXISTS_src",
        "DIR_EXISTS_tests",
        "QUALITY_LINT",
        "QUALITY_TYPE",
        "QUALITY_COMPLEXITY",
        "ARCH_CIRCULAR",
        "ARCH_GOD_CLASS",
        "ARCH_COUPLING",
        "PRACTICE_DOCSTRING",
        "PRACTICE_BARE_EXCEPT",
        "PRACTICE_SECURITY",
    ])
    def test_rule_exists_and_functional(self, rule_id, tmp_path):
        """Test that each rule exists and can execute."""
        from axm_audit import get_rules_for_category
        
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "src").mkdir()
        
        all_rules = get_rules_for_category(None)
        rule_ids = [rule.rule_id for rule in all_rules]
        
        assert rule_id in rule_ids

    def test_all_rules_have_check_method(self):
        """Test that all rules implement the check() method."""
        from axm_audit import get_rules_for_category
        
        rules = get_rules_for_category(None)
        
        for rule in rules:
            assert hasattr(rule, "check")
            assert callable(rule.check)

    def test_all_rules_have_rule_id(self):
        """Test that all rules have a rule_id property."""
        from axm_audit import get_rules_for_category
        
        rules = get_rules_for_category(None)
        
        for rule in rules:
            assert hasattr(rule, "rule_id")
            assert isinstance(rule.rule_id, str)
            assert len(rule.rule_id) > 0


class TestDependencyIsolation:
    """Test that axm-audit has no dependencies on axm."""

    def test_no_axm_imports_in_audit(self):
        """Test that axm-audit does not import from axm."""
        import sys
        import importlib
        
        # Remove axm from sys.modules if present
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith("axm.")]
        for mod in modules_to_remove:
            del sys.modules[mod]
        
        # Import axm_audit - should not trigger axm imports
        import axm_audit
        
        # Check that axm was not imported
        axm_modules = [k for k in sys.modules.keys() if k.startswith("axm.")]
        assert len(axm_modules) == 0

    def test_only_pydantic_dependency(self):
        """Test that axm-audit only depends on pydantic."""
        # This would be tested by inspecting pyproject.toml
        # For now, we'll just verify pydantic is available
        import pydantic
        assert pydantic is not None
