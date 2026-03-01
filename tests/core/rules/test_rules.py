"""Tests for rules — registration and functional checks."""

from __future__ import annotations

import pytest


class TestRulesRegistration:
    """Test that all rules are registered and functional."""

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
            "PRACTICE_LOGGING",
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

    def test_all_rules_registered(self) -> None:
        """AC1: get_rules_for_category(None) returns all expected rule instances."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = {r.rule_id for r in rules}

        # 18 non-tooling rule IDs + 3 tooling = 21 total entries
        expected_non_tooling = {
            "STRUCTURE_PYPROJECT",
            "QUALITY_LINT",
            "QUALITY_FORMAT",
            "QUALITY_TYPE",
            "QUALITY_COMPLEXITY",
            "QUALITY_DIFF_SIZE",
            "QUALITY_SECURITY",
            "QUALITY_COVERAGE",
            "DEPS_AUDIT",
            "DEPS_HYGIENE",
            "ARCH_CIRCULAR",
            "ARCH_GOD_CLASS",
            "ARCH_COUPLING",
            "ARCH_DUPLICATION",
            "PRACTICE_DOCSTRING",
            "PRACTICE_BARE_EXCEPT",
            "PRACTICE_SECURITY",
            "PRACTICE_BLOCKING_IO",
            "PRACTICE_LOGGING",
        }
        assert expected_non_tooling.issubset(rule_ids), (
            f"Missing rules: {expected_non_tooling - rule_ids}"
        )
        # Tooling rules are dynamic (TOOLING_ruff, TOOLING_mypy, TOOLING_uv)
        tooling_ids = {rid for rid in rule_ids if rid.startswith("TOOL_")}
        assert len(tooling_ids) >= 3

    def test_category_filter_includes_new_rules(self) -> None:
        """Practice category includes BlockingIORule and LoggingPresenceRule."""
        from axm_audit import get_rules_for_category

        practice_rules = get_rules_for_category("practice")
        rule_ids = {r.rule_id for r in practice_rules}

        assert "PRACTICE_BLOCKING_IO" in rule_ids
        assert "PRACTICE_LOGGING" in rule_ids
        assert "PRACTICE_DOCSTRING" in rule_ids

    def test_quick_mode_skips_new_rules(self) -> None:
        """Edge case: quick=True only returns LintingRule + TypeCheckRule."""
        from axm_audit import get_rules_for_category

        quick_rules = get_rules_for_category(None, quick=True)
        rule_ids = {r.rule_id for r in quick_rules}

        assert rule_ids == {"QUALITY_LINT", "QUALITY_TYPE"}

    def test_all_rules_have_check_method(self) -> None:
        """Test that all rules implement the check() method."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)

        for rule in rules:
            assert hasattr(rule, "check")
            assert callable(rule.check)

    def test_all_rules_have_rule_id(self) -> None:
        """Test that all rules have a rule_id property."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)

        for rule in rules:
            assert hasattr(rule, "rule_id")
            assert isinstance(rule.rule_id, str)
            assert len(rule.rule_id) > 0

    def test_safe_check_catches_exceptions(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Edge case: _safe_check returns ERROR result when rule raises."""
        from pathlib import Path

        from axm_audit.core.auditor import _safe_check
        from axm_audit.core.rules.base import ProjectRule
        from axm_audit.models.results import CheckResult

        class CrashingRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "TEST_CRASH"

            @property
            def category(self) -> str:
                return "testing"

            def check(self, project_path: Path) -> CheckResult:
                msg = "intentional crash"
                raise RuntimeError(msg)

        result = _safe_check(CrashingRule(), tmp_path)  # type: ignore[arg-type]
        assert not result.passed
        assert "crashed" in result.message.lower()
        assert result.fix_hint is not None


class TestRuleRegistryDeduplication:
    """Tests for auto-discovery registry (AXM-198)."""

    def test_all_rules_derived_from_registry(self) -> None:
        """AC: all-rules derived from get_registry()."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit import get_rules_for_category
        from axm_audit.core.auditor import _get_tooling_rules
        from axm_audit.core.rules.base import get_registry

        all_rules = get_rules_for_category(None)
        all_rule_types = {type(r) for r in all_rules}

        # Build expected set from registry
        registry = get_registry()
        expected_types: set[type] = set()
        for cat, rule_classes in registry.items():
            if cat == "tooling":
                expected_types.update(type(r) for r in _get_tooling_rules())
            else:
                expected_types.update(rule_classes)

        assert all_rule_types == expected_types, (
            f"Mismatch: extra={all_rule_types - expected_types}, "
            f"missing={expected_types - all_rule_types}"
        )

    def test_no_manual_rule_enumeration(self) -> None:
        """AC: all-rules path has no manual enumeration — count matches registry."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit import get_rules_for_category
        from axm_audit.core.auditor import _get_tooling_rules
        from axm_audit.core.rules.base import get_registry

        all_rules = get_rules_for_category(None)

        # Expected count: sum of all registry rule classes,
        # with tooling expanded to 3 instances
        registry = get_registry()
        expected_count = sum(
            len(_get_tooling_rules()) if cat == "tooling" else len(classes)
            for cat, classes in registry.items()
        )
        assert len(all_rules) == expected_count

    @pytest.mark.parametrize(
        "category,expected_count",
        [
            ("structure", 1),
            ("quality", 6),
            ("architecture", 4),
            ("practice", 6),
            ("security", 1),
            ("dependencies", 2),
            ("testing", 1),
            ("tooling", 3),
        ],
    )
    def test_category_filter_unchanged(
        self, category: str, expected_count: int
    ) -> None:
        """Regression: each category returns the exact rule count."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(category)
        assert len(rules) == expected_count, (
            f"Category '{category}': expected {expected_count}, got {len(rules)}"
        )
