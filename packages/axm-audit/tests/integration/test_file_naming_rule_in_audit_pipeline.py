"""Integration tests asserting FileNamingRule plugs into the audit pipeline."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.tools.audit import AuditTool

pytestmark = pytest.mark.integration

_PYPROJECT = (
    textwrap.dedent(
        """
    [project]
    name = "mypkg"
    version = "0"
    """
    ).strip()
    + "\n"
)


def _seed_pkg(project: Path) -> None:
    (project / "src" / "mypkg").mkdir(parents=True, exist_ok=True)
    (project / "src" / "mypkg" / "__init__.py").write_text("class Rule:\n    pass\n")
    (project / "pyproject.toml").write_text(_PYPROJECT)


def _rule_ids_in(result: dict[str, object]) -> set[str]:
    """Extract the set of rule_ids appearing in an AuditTool agent result.

    The agent format splits checks into ``passed`` (string ``rule_id: msg``
    or dict with ``rule_id``) and ``failed`` (dict with ``rule_id``).
    """
    ids: set[str] = set()
    for bucket in ("passed", "failed", "checks", "results", "findings", "rules"):
        items = result.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and "rule_id" in item:
                ids.add(str(item["rule_id"]))
            elif isinstance(item, str) and ":" in item:
                ids.add(item.split(":", 1)[0].strip())
    return ids


def test_audit_test_quality_surfaces_new_rule(tmp_path: Path) -> None:
    """AC11 — audit(category='test_quality') reports the new rule."""
    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_rule.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    tool = AuditTool()
    tool_result = tool.execute(path=str(project), category="test_quality")
    data = tool_result.data if hasattr(tool_result, "data") else tool_result
    assert isinstance(data, dict)
    assert "TEST_QUALITY_FILE_NAMING" in _rule_ids_in(data)


def test_no_overlap_with_no_package_symbol(tmp_path: Path) -> None:
    """AC11 — NAME_MISMATCH and NO_PACKAGE_SYMBOL are orthogonal.

    A file whose name diverges from its canonical but DOES exercise the
    package should be flagged by FILE_NAMING and ignored by
    NO_PACKAGE_SYMBOL.
    """
    from axm_audit.core.rules.test_quality.file_naming import FileNamingRule
    from axm_audit.core.rules.test_quality.no_package_symbol import (
        NoPackageSymbolRule,
    )

    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_unexpected.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    naming = FileNamingRule().check(project)
    no_sym = NoPackageSymbolRule().check(project)

    naming_findings = list(naming.details.get("findings", [])) if naming.details else []
    no_sym_findings = list(no_sym.details.get("findings", [])) if no_sym.details else []

    assert any(f["verdict"] == "NAME_MISMATCH" for f in naming_findings), (
        "FILE_NAMING should flag the divergent name"
    )
    assert no_sym_findings == [], (
        "NO_PACKAGE_SYMBOL must not flag a test that exercises the package"
    )
