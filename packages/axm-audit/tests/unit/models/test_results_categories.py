from __future__ import annotations

from axm_audit.models.results import (
    _CATEGORY_WEIGHTS,
    EXTRA_NONSCORED_CATEGORIES,
    SCORED_CATEGORIES,
)


def test_scored_categories_match_weights() -> None:
    assert SCORED_CATEGORIES == frozenset(_CATEGORY_WEIGHTS)


def test_extra_nonscored_categories_are_disjoint() -> None:
    assert SCORED_CATEGORIES.isdisjoint(EXTRA_NONSCORED_CATEGORIES)
