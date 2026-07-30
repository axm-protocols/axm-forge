"""Split from ``test_auditor_categories.py``."""

from pathlib import Path

from axm_audit.core.auditor import audit_project
from axm_audit.models.results import SCORED_CATEGORIES


def test_audit_project_accepts_each_scored_category(minimal_pkg: Path) -> None:
    assert "test_quality" in SCORED_CATEGORIES
    for cat in SCORED_CATEGORIES:
        result = audit_project(minimal_pkg, category=cat)
        assert result.checks, f"category {cat!r} produced no checks"
        observed = {c.category for c in result.checks}
        assert observed == {cat}, (
            f"category={cat!r} returned checks from other categories: {observed}"
        )
