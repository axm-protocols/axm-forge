"""Tests for core auditor functionality."""

from __future__ import annotations

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


class TestMergeMetadata:
    """Test the _merge_metadata() helper used by workspace aggregation."""

    def test_merge_metadata_concatenates_lists(self):
        """Lists at the same key are concatenated, existing first."""
        from axm_audit.core.auditor import _merge_metadata

        a = {"verdicts": [1, 2]}
        b = {"verdicts": [3]}

        assert _merge_metadata(a, b) == {"verdicts": [1, 2, 3]}

    def test_merge_metadata_recurses_into_dicts(self):
        """Nested dicts merge recursively, lists at leaves concatenate."""
        from axm_audit.core.auditor import _merge_metadata

        a = {"x": {"k": [1]}}
        b = {"x": {"k": [2]}}

        assert _merge_metadata(a, b) == {"x": {"k": [1, 2]}}

    def test_merge_metadata_scalar_b_wins(self):
        """For scalar values at the same key, incoming (b) overrides existing (a)."""
        from axm_audit.core.auditor import _merge_metadata

        a = {"k": 1}
        b = {"k": 2}

        assert _merge_metadata(a, b) == {"k": 2}

    def test_merge_metadata_handles_none_inputs(self):
        """None inputs are treated as empty dicts; (None, None) returns {}."""
        from axm_audit.core.auditor import _merge_metadata

        assert _merge_metadata(None, {"k": 1}) == {"k": 1}
        assert _merge_metadata({"k": 1}, None) == {"k": 1}
        assert _merge_metadata(None, None) == {}
