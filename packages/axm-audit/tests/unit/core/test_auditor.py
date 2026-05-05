"""Tests for core auditor functionality."""

from pathlib import Path

import pytest


class TestAuditProjectFunctionUnit:
    """Test the main audit_project() function in axm-audit (unit-level)."""

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

    def test_audit_project_nonexistent_path_raises_error(self):
        """Test that audit_project raises FileNotFoundError for invalid path."""
        from axm_audit import audit_project

        with pytest.raises(FileNotFoundError):
            audit_project(Path("/nonexistent/path"))


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
        assert len(rules) == 29

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
