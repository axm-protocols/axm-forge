from __future__ import annotations

from axm_audit.core.auditor import VALID_CATEGORIES
from axm_audit.models.results import (
    EXTRA_NONSCORED_CATEGORIES,
    SCORED_CATEGORIES,
)


def test_valid_categories_is_union() -> None:
    assert VALID_CATEGORIES == SCORED_CATEGORIES | EXTRA_NONSCORED_CATEGORIES


def test_get_rules_for_category_test_quality_returns_registered_rules() -> None:
    from axm_audit.core.auditor import get_rules_for_category

    rules = get_rules_for_category("test_quality")
    rule_ids = {r.rule_id for r in rules}
    expected = {
        "TEST_QUALITY_DUPLICATE_TESTS",
        "TEST_QUALITY_PRIVATE_IMPORTS",
        "TEST_QUALITY_PYRAMID_LEVEL",
        "TEST_QUALITY_TAUTOLOGY",
    }
    assert expected <= rule_ids
