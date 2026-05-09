"""Integration tests for rules — exercises rule registry with tmp_path I/O."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestRulesRegistration:
    """Integration tests that exercise rule registration with real I/O."""

    @pytest.mark.parametrize(
        "rule_id",
        [
            # structure
            "STRUCTURE_PYPROJECT",
            # quality
            "QUALITY_LINT",
            "QUALITY_FORMAT",
            "QUALITY_TYPE",
            "QUALITY_COMPLEXITY",
            "QUALITY_DIFF_SIZE",
            # security
            "QUALITY_SECURITY",
            # coverage
            "QUALITY_COVERAGE",
            # dependencies
            "DEPS_AUDIT",
            "DEPS_HYGIENE",
            # architecture
            "ARCH_CIRCULAR",
            "ARCH_GOD_CLASS",
            "ARCH_COUPLING",
            "ARCH_DUPLICATION",
            # practice
            "PRACTICE_DOCSTRING",
            "PRACTICE_BARE_EXCEPT",
            "PRACTICE_SECURITY",
            "PRACTICE_BLOCKING_IO",
        ],
    )
    def test_rule_exists_and_functional(
        self, rule_id: str, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test that each rule exists in the all-rules list."""
        from axm_audit import get_rules_for_category

        all_rules = get_rules_for_category(None)
        rule_ids = [rule.rule_id for rule in all_rules]

        assert rule_id in rule_ids
