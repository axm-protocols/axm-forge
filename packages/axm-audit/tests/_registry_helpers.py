"""Shared helpers for registry-derived test data.

Builds rule_id -> category mappings dynamically from get_registry()
instead of hardcoding them in each test module.
"""

from __future__ import annotations

import axm_audit.core.rules  # noqa: F401 — trigger @register_rule
from axm_audit.core.rules.base import get_registry

__all__ = ["SCORED_CATEGORIES", "build_rule_category_map", "scored_rule_ids"]

# Categories that contribute to quality_score (matches results.py:88-97).
# Excludes structure and tooling.
SCORED_CATEGORIES: frozenset[str] = frozenset(
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


def build_rule_category_map() -> dict[str, str]:
    """Build rule_id -> category mapping from the live registry.

    Filters to scored categories only (excludes structure, tooling).
    Skips rules whose constructors require parameters.
    """
    mapping: dict[str, str] = {}
    for category, rule_classes in get_registry().items():
        if category not in SCORED_CATEGORIES:
            continue
        for cls in rule_classes:
            try:
                rule = cls()
            except TypeError:
                continue
            mapping[rule.rule_id] = rule.category
    return mapping


def scored_rule_ids() -> list[str]:
    """Return all scored rule IDs from the registry."""
    return list(build_rule_category_map().keys())
