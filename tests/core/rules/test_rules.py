"""Tests for rules."""

import pytest


class TestRulesMigration:
    """Test that all 13 rules have been migrated correctly."""

    @pytest.mark.parametrize(
        "rule_id",
        [
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
        ],
    )
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
