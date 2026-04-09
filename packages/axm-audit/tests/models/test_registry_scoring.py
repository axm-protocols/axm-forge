"""Tests for registry-derived scoring — no hardcoded rule lists.

Verifies that quality_score and grade work correctly when scored rule
lists are built dynamically from get_registry(), ensuring resilience
to rule additions and removals.
"""

from __future__ import annotations

import pytest

import axm_audit.core.rules  # noqa: F401 — trigger @register_rule
from axm_audit.core.rules.base import get_registry
from axm_audit.models.results import AuditResult, CheckResult

# Categories that contribute to quality_score (matches results.py)
_SCORED_CATEGORIES: frozenset[str] = frozenset(
    {
        "lint",
        "type",
        "complexity",
        "security",
        "deps",
        "testing",
        "architecture",
        "practices",
    }
)


def _build_rule_category_map() -> dict[str, str]:
    """Build rule_id -> category mapping from the live registry.

    Filters to scored categories only (excludes structure, tooling).
    Handles rules with required constructor params by skipping them.
    """
    mapping: dict[str, str] = {}
    for category, rule_classes in get_registry().items():
        if category not in _SCORED_CATEGORIES:
            continue
        for cls in rule_classes:
            try:
                rule = cls()
            except TypeError:
                continue
            mapping[rule.rule_id] = rule.category
    return mapping


def _scored_rule_ids() -> list[str]:
    """Return all scored rule IDs from the registry."""
    return list(_build_rule_category_map().keys())


def _make_check(
    rule_id: str, score: float, category_map: dict[str, str]
) -> CheckResult:
    """Create a CheckResult with score and category from the registry map."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        details={"score": score},
        category=category_map.get(rule_id),
    )


class TestRegistryDerivedScoring:
    """Scoring tests that derive rule lists from get_registry()."""

    def test_all_perfect_scores_100(self) -> None:
        """All scored rules at 100 via registry -> quality_score == 100.0."""
        category_map = _build_rule_category_map()
        checks = [_make_check(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_all_zero_scores_grade_f(self) -> None:
        """All scored rules at 0 via registry -> grade == 'F'."""
        category_map = _build_rule_category_map()
        checks = [_make_check(rid, 0, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == pytest.approx(0.0, abs=0.1)
        assert result.grade == "F"

    def test_registry_covers_all_scored_categories(self) -> None:
        """Registry must provide at least one rule per scored category."""
        category_map = _build_rule_category_map()
        covered = set(category_map.values())
        missing = _SCORED_CATEGORIES - covered
        assert not missing, f"Scored categories missing from registry: {missing}"

    def test_rule_addition_no_test_change(self) -> None:
        """Adding a rule to the registry doesn't break scoring tests.

        This is structural: the test itself proves resilience because
        it derives everything from the registry. If a new rule is added,
        it will be automatically included in the checks list.
        """
        category_map = _build_rule_category_map()
        assert len(category_map) > 0, "Registry should have at least one scored rule"
        checks = [_make_check(rid, 100, category_map) for rid in category_map]
        result = AuditResult(checks=checks)
        assert result.quality_score == 100.0

    def test_scored_rule_ids_non_empty(self) -> None:
        """_scored_rule_ids must return a non-empty list."""
        ids = _scored_rule_ids()
        assert len(ids) > 0
        # Each ID should be a non-empty string
        for rid in ids:
            assert isinstance(rid, str)
            assert len(rid) > 0
