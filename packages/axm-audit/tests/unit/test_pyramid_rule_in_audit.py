from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project, get_rules_for_category
from axm_audit.core.rules.structure import TestsPyramidRule

__all__ = []

pytestmark = pytest.mark.integration


PYPROJECT = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"

    [tool.pytest.ini_options]
    markers = [
        "integration: integration tests",
        "e2e: end-to-end tests",
    ]
    """
).strip()


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    for d in ("tests/unit", "tests/integration", "tests/e2e"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")
    return tmp_path


def test_pyramid_rule_registered_in_structure_category() -> None:
    rules = get_rules_for_category("structure")
    assert any(isinstance(r, TestsPyramidRule) for r in rules)


def test_audit_project_reports_pyramid_verdict(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    result = audit_project(project, category="structure")
    pyramid_rule_id = TestsPyramidRule().rule_id
    matching = [c for c in result.checks if c.rule_id == pyramid_rule_id]
    assert len(matching) == 1
