"""Tests for core auditor functionality."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from axm_audit.core.auditor import VALID_CATEGORIES, get_rules_for_category
from axm_audit.models.results import (
    EXTRA_NONSCORED_CATEGORIES,
    SCORED_CATEGORIES,
    CheckResult,
    Severity,
)


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
        assert len(rules) == 31

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
    """Test the merge_metadata() helper used by workspace aggregation."""

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            pytest.param(
                {"verdicts": [1, 2]},
                {"verdicts": [3]},
                {"verdicts": [1, 2, 3]},
                id="concatenates_lists",
            ),
            pytest.param(
                {"x": {"k": [1]}},
                {"x": {"k": [2]}},
                {"x": {"k": [1, 2]}},
                id="recurses_into_dicts",
            ),
            pytest.param(
                {"k": 1},
                {"k": 2},
                {"k": 2},
                id="scalar_b_wins",
            ),
        ],
    )
    def test_merge_metadata_combines_inputs(self, a, b, expected):
        """merge_metadata: list-concat, dict-recursion, and scalar-b-wins semantics."""
        from axm_audit.core.auditor import merge_metadata

        assert merge_metadata(a, b) == expected

    def test_merge_metadata_handles_none_inputs(self):
        """None inputs are treated as empty dicts; (None, None) returns {}."""
        from axm_audit.core.auditor import merge_metadata

        assert merge_metadata(None, {"k": 1}) == {"k": 1}
        assert merge_metadata({"k": 1}, None) == {"k": 1}
        assert merge_metadata(None, None) == {}


# ---------------------------------------------------------------------------
# Merged from test_auditor_categories.py
# ---------------------------------------------------------------------------


def test_valid_categories_is_union() -> None:
    assert VALID_CATEGORIES == SCORED_CATEGORIES | EXTRA_NONSCORED_CATEGORIES


def test_get_rules_for_category_test_quality_returns_registered_rules() -> None:
    rules = get_rules_for_category("test_quality")
    rule_ids = {r.rule_id for r in rules}
    expected = {
        "TEST_QUALITY_DUPLICATE_TESTS",
        "TEST_QUALITY_PRIVATE_IMPORTS",
        "TEST_QUALITY_PYRAMID_LEVEL",
        "TEST_QUALITY_TAUTOLOGY",
    }
    assert expected <= rule_ids


# ---------------------------------------------------------------------------
# Merged from test_auditor_integration_security.py
# ---------------------------------------------------------------------------


def test_security_pattern_rule_in_security_category():
    """SecurityPatternRule should be in the security category."""
    rules = get_rules_for_category("security")
    rule_types = [type(r).__name__ for r in rules]
    assert "SecurityPatternRule" in rule_types


# ---------------------------------------------------------------------------
# Merged from test_auditor_test_quality_category.py
# ---------------------------------------------------------------------------


def test_get_rules_for_category_test_quality_empty_ok() -> None:
    """test_quality is a valid category and returns a list of registered rules."""
    rules = get_rules_for_category("test_quality")
    assert isinstance(rules, list)
    assert all(hasattr(r, "check") for r in rules), (
        "Every test_quality rule must expose a `.check` method"
    )


def test_get_rules_for_category_test_quality_picks_up_registrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rules registered under test_quality are surfaced by get_rules_for_category."""
    from axm_audit.core import auditor as auditor_module
    from axm_audit.core.rules.quality import LintingRule

    fake_registry = {"test_quality": [LintingRule]}
    monkeypatch.setattr(auditor_module, "get_registry", lambda: fake_registry)

    rules = get_rules_for_category("test_quality")

    assert len(rules) >= 1


# ---------------------------------------------------------------------------
# Merged from test_auditor_workspace_merge.py
# ---------------------------------------------------------------------------


class TestMergeCheckPreservesFindings:
    """``merge_check`` concatenates ``findings`` lists.

    Ordering is (existing, incoming).
    """

    def test_workspace_aggregate_concatenates_findings(self):
        """AC4 — findings from both packages survive concatenation."""
        from axm_audit.core.auditor import merge_check
        from axm_audit.core.rules.test_quality.pyramid_level import (
            Finding,
            PyramidCheckResult,
        )

        finding_a = Finding(
            path="packages/a/tests/unit/test_x.py",
            function="test_x",
            level="unit",
            reason="bad",
            current_level="unit",
            has_real_io=False,
            has_subprocess=False,
        )
        finding_b = Finding(
            path="packages/b/tests/unit/test_y.py",
            function="test_y",
            level="unit",
            reason="bad",
            current_level="unit",
            has_real_io=False,
            has_subprocess=False,
        )
        existing = PyramidCheckResult(
            rule_id="r",
            passed=False,
            message="m",
            findings=[finding_a],
        )
        incoming = PyramidCheckResult(
            rule_id="r",
            passed=False,
            message="m",
            findings=[finding_b],
        )

        merged = cast(PyramidCheckResult, merge_check(existing, incoming, "b"))

        assert [f.path for f in merged.findings] == [
            "packages/a/tests/unit/test_x.py",
            "[b] packages/b/tests/unit/test_y.py",
        ] or [f.path for f in merged.findings] == [
            finding_a.path,
            finding_b.path,
        ]
        assert len(merged.findings) == 2


class TestMergeCheckExistingSemanticsUnchanged:
    """AC5 — pre-existing merge semantics for passed/score/severity/text/details."""

    def test_existing_merge_semantics_unchanged(self):
        """AC5 — worst-of-N for passed/score/severity, joined text, shallow details."""
        from axm_audit.core.auditor import merge_check

        existing = CheckResult(
            rule_id="r",
            passed=True,
            message="m",
            severity=Severity.WARNING,
            text="alpha",
            details={"x": 1, "y": 2},
            score=80,
        )
        incoming = CheckResult(
            rule_id="r",
            passed=False,
            message="m",
            severity=Severity.ERROR,
            text="beta",
            details={"y": 99, "z": 3},
            score=40,
        )

        merged = merge_check(existing, incoming, "b")

        assert merged.passed is False
        assert merged.score == 40
        assert merged.severity == Severity.ERROR
        assert merged.text is not None
        assert "alpha" in merged.text
        assert "beta" in merged.text
        assert merged.details is not None
        assert merged.details["x"] == 1
        assert merged.details["y"] == 99
        assert merged.details["z"] == 3


# ---------------------------------------------------------------------------
# Merged from tests/unit/core/rules/test_rules.py
# ---------------------------------------------------------------------------


class TestRulesRegistration:
    """Test that all rules are registered and functional."""

    def test_all_rules_registered(self) -> None:
        """AC1: get_rules_for_category(None) returns all expected rule instances."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = {r.rule_id for r in rules}

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
        }
        assert expected_non_tooling.issubset(rule_ids), (
            f"Missing rules: {expected_non_tooling - rule_ids}"
        )
        tooling_ids = {rid for rid in rule_ids if rid.startswith("TOOL_")}
        assert len(tooling_ids) >= 3

    def test_category_filter_includes_new_rules(self) -> None:
        """Practices category includes BlockingIORule but not LoggingPresenceRule."""
        from axm_audit import get_rules_for_category

        practice_rules = get_rules_for_category("practices")
        rule_ids = {r.rule_id for r in practice_rules}

        assert "PRACTICE_BLOCKING_IO" in rule_ids
        assert "PRACTICE_LOGGING" not in rule_ids
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


class TestRuleRegistryDeduplication:
    """Tests for auto-discovery registry (AXM-198)."""

    def test_all_rules_derived_from_registry(self) -> None:
        """AC: all-rules derived from get_registry()."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit import get_rules_for_category
        from axm_audit.core.rules.base import get_registry

        all_rules = get_rules_for_category(None)
        all_rule_types = {type(r) for r in all_rules}

        registry = get_registry()
        expected_types: set[type] = set()
        for _cat, rule_classes in registry.items():
            for cls in rule_classes:
                expected_types.update(type(r) for r in cls.get_instances())

        assert all_rule_types == expected_types, (
            f"Mismatch: extra={all_rule_types - expected_types}, "
            f"missing={expected_types - all_rule_types}"
        )

    def test_no_manual_rule_enumeration(self) -> None:
        """AC: all-rules path has no manual enumeration — count matches registry."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit import get_rules_for_category
        from axm_audit.core.rules.base import get_registry

        all_rules = get_rules_for_category(None)

        registry = get_registry()
        expected_count = sum(
            len(cls.get_instances()) for classes in registry.values() for cls in classes
        )
        assert len(all_rules) == expected_count

    @pytest.mark.parametrize(
        "category,expected_count",
        [
            ("lint", 4),
            ("type", 1),
            ("complexity", 1),
            ("security", 2),
            ("deps", 2),
            ("testing", 1),
            ("architecture", 4),
            ("practices", 5),
            ("structure", 2),
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


class TestGetInstances:
    """Tests for get_instances() classmethod (AXM-202)."""

    def test_get_instances_default(self) -> None:
        """Default get_instances() returns [cls()]."""
        from axm_audit.core.rules.quality import LintingRule

        instances = LintingRule.get_instances()
        assert len(instances) == 1
        assert isinstance(instances[0], LintingRule)

    def test_get_instances_tooling(self) -> None:
        """ToolAvailabilityRule.get_instances() returns 3 tool instances."""
        from axm_audit.core.rules.tooling import ToolAvailabilityRule

        instances = ToolAvailabilityRule.get_instances()
        assert len(instances) == 3
        tool_names = {r.tool_name for r in instances}
        assert tool_names == {"ruff", "mypy", "uv"}

    def test_duplication_rule_category_from_registry(self) -> None:
        """DuplicationRule category comes from @register_rule, not override."""
        from axm_audit.core.rules.duplication import DuplicationRule

        rule = DuplicationRule()
        assert rule.category == "architecture"

    def test_all_rules_includes_tooling(self) -> None:
        """All-rules path includes TOOL_RUFF, TOOL_MYPY, TOOL_UV."""
        from axm_audit import get_rules_for_category

        rules = get_rules_for_category(None)
        rule_ids = {r.rule_id for r in rules}
        assert "TOOL_RUFF" in rule_ids
        assert "TOOL_MYPY" in rule_ids
        assert "TOOL_UV" in rule_ids


# --- audit_project: empty category test_quality on axm-audit itself ---


def test_audit_category_empty_rules_returns_valid_result() -> None:
    from pathlib import Path

    from axm_audit.core.auditor import audit_project

    pkg_root = Path(__file__).resolve().parents[3]
    result = audit_project(pkg_root, category="test_quality")
    assert result is not None
    assert hasattr(result, "checks")
    assert isinstance(result.checks, list)
