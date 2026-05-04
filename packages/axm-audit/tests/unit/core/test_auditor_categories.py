from __future__ import annotations

import pytest

from axm_audit.core.auditor import VALID_CATEGORIES, audit_project
from axm_audit.models.results import (
    EXTRA_NONSCORED_CATEGORIES,
    SCORED_CATEGORIES,
)


@pytest.fixture
def minimal_pkg(tmp_path):
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    return pkg


def test_valid_categories_is_union() -> None:
    assert VALID_CATEGORIES == SCORED_CATEGORIES | EXTRA_NONSCORED_CATEGORIES


def test_audit_project_accepts_each_scored_category(minimal_pkg) -> None:
    from axm_audit.models.results import AuditResult

    for cat in SCORED_CATEGORIES:
        result = audit_project(minimal_pkg, category=cat)
        assert isinstance(result, AuditResult)


def test_audit_project_rejects_unknown_category(minimal_pkg) -> None:
    with pytest.raises((ValueError, KeyError)):
        audit_project(minimal_pkg, category="bogus")
