"""Integration tests for CheckResult.text propagation through audit_project.

Real filesystem + ruff subprocess invocations live here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_failed_rules_produce_text(tmp_path: Path) -> None:
    """audit_project(category='lint') on a dirty project fills text on failures."""
    from axm_audit.core.auditor import audit_project

    # Create a minimal Python project with a lint violation
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text("import os\nimport sys\n")  # unused imports
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1.0"\n[tool.ruff]\nselect = ["F"]\n'
    )

    result = audit_project(tmp_path, category="lint")

    failed = [c for c in result.checks if not c.passed]
    assert failed, "Expected at least one failed check for lint violations"
    for c in failed:
        assert c.text is not None, f"{c.rule_id} failed but text is None"
