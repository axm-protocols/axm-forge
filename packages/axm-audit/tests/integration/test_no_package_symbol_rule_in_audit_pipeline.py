"""Integration test: the new rule surfaces through the audit pipeline (AC10)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.tools.audit import AuditTool

pytestmark = pytest.mark.integration


def _layout_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg-proj"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("def fn() -> int:\n    return 1\n")
    (pkg / "tests" / "integration").mkdir(parents=True)
    (pkg / "tests" / "integration" / "test_x.py").write_text(
        "from pkg import fn\n\ndef test_x():\n    assert fn() == 1\n"
    )
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            pkg-cli = "pkg.cli:main"
            """
        ).strip()
    )
    return pkg


def test_audit_test_quality_surfaces_new_rule(tmp_path: Path) -> None:
    """AC10: audit(category="test_quality") includes the new rule."""
    pkg = _layout_pkg(tmp_path)
    tool = AuditTool()
    result = tool.execute(path=str(pkg), category="test_quality")
    payload = result.data if isinstance(result.data, dict) else {}
    rules_seen: set[str] = set()
    for key in ("rules", "results", "checks", "findings"):
        items = payload.get(key) or []
        for entry in items:
            if isinstance(entry, dict):
                rid = entry.get("rule_id") or entry.get("id")
                if isinstance(rid, str):
                    rules_seen.add(rid)
    text_blob = (result.text or "") + str(payload)
    assert "TEST_QUALITY_NO_PACKAGE_SYMBOL" in rules_seen or (
        "TEST_QUALITY_NO_PACKAGE_SYMBOL" in text_blob
    ), "new rule did not surface in audit pipeline"
