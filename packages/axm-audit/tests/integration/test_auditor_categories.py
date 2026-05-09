from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.models.results import SCORED_CATEGORIES

pytestmark = pytest.mark.integration


@pytest.fixture
def minimal_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    return pkg


def test_audit_project_accepts_each_scored_category(minimal_pkg: Path) -> None:
    assert "test_quality" in SCORED_CATEGORIES
    for cat in SCORED_CATEGORIES:
        result = audit_project(minimal_pkg, category=cat)
        assert result.checks, f"category {cat!r} produced no checks"
        observed = {c.category for c in result.checks}
        assert observed == {cat}, (
            f"category={cat!r} returned checks from other categories: {observed}"
        )


def test_audit_project_test_quality_returns_test_quality_rules(
    minimal_pkg: Path,
) -> None:
    result = audit_project(minimal_pkg, category="test_quality")
    rule_ids = {c.rule_id for c in result.checks}
    expected = {
        "TEST_QUALITY_DUPLICATE_TESTS",
        "TEST_QUALITY_PRIVATE_IMPORTS",
        "TEST_QUALITY_PYRAMID_LEVEL",
        "TEST_QUALITY_TAUTOLOGY",
    }
    assert expected <= rule_ids, f"missing test_quality rules: {expected - rule_ids}"


def test_audit_project_rejects_unknown_category(minimal_pkg: Path) -> None:
    with pytest.raises((ValueError, KeyError)):
        audit_project(minimal_pkg, category="bogus")


def test_audit_project_invalid_category_lists_test_quality(minimal_pkg: Path) -> None:
    with pytest.raises(ValueError) as exc_info:
        audit_project(minimal_pkg, category="bogus")
    msg = str(exc_info.value)
    assert "test_quality" in msg
    assert "testing" in msg
