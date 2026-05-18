"""Split from ``test_file_naming_rule_in_audit_pipeline.py``."""

import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.tools.audit import AuditTool
from tests.integration._helpers import _PYPROJECT


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


def test_execute_valid_project(tmp_path: Path) -> None:
    """AuditTool on a valid project returns success with data."""
    from axm_audit.tools.audit import AuditTool

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "test-pkg"\n'
        'version = "0.1.0"\n'
        'description = "Test"\n'
        'requires-python = ">=3.12"\n'
    )

    tool = AuditTool()
    result = tool.execute(path=str(tmp_path))

    assert result.success is True
    assert result.data is not None
    assert "score" in result.data
    assert "grade" in result.data


def test_execute_not_a_directory(tmp_path: Path) -> None:
    """AuditTool on a non-directory path returns failure."""
    from axm_audit.tools.audit import AuditTool

    fake_path = tmp_path / "nonexistent"

    tool = AuditTool()
    result = tool.execute(path=str(fake_path))

    assert result.success is False
    assert result.error is not None
    assert "Not a directory" in result.error


def test_execute_with_category_filter(tmp_path: Path) -> None:
    """AuditTool with category filter runs only that category."""
    from axm_audit.tools.audit import AuditTool

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
    )

    tool = AuditTool()
    result = tool.execute(path=str(tmp_path), category="structure")

    assert result.success is True
    assert result.data is not None


@pytest.fixture()
def mock_audit_project(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock audit_project to return a minimal AuditResult."""
    check_pass = MagicMock(
        passed=True,
        rule_id="QUALITY_LINT",
        message="Lint score: 100/100 (0 issues)",
        text=None,
        details=None,
        fix_hint=None,
    )
    check_fail = MagicMock(
        passed=False,
        rule_id="QUALITY_COMPLEXITY",
        message="2 functions exceed CC threshold",
        text="src/a.py:10 func CC=15",
        details=None,
        fix_hint="Extract helpers",
    )
    mock_result = MagicMock(
        checks=[check_pass, check_fail],
        quality_score=80,
        grade="B",
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: mock_result
    )
    return mock_result


def test_audit_tool_returns_text(mock_audit_project: MagicMock, tmp_path: Any) -> None:
    project = tmp_path / "project"
    project.mkdir()
    result = AuditTool().execute(path=str(project))
    assert result.success
    assert result.text is not None
    # Header contains "audit" keyword
    header = result.text.splitlines()[0]
    assert "audit" in header
    # data dict still present for backward compat
    assert result.data is not None
    assert "passed" in result.data
    assert "failed" in result.data


def test_audit_tool_text_with_category(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    check = MagicMock(
        passed=True,
        rule_id="STRUCT_LAYOUT",
        message="Layout OK",
        text=None,
        details=None,
        fix_hint=None,
    )
    mock_result = MagicMock(
        checks=[check],
        quality_score=100,
        grade="A",
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: mock_result
    )
    project = tmp_path / "cat_project"
    project.mkdir()
    result = AuditTool().execute(path=str(project), category="structure")
    assert result.success
    assert result.text is not None
    assert result.text.startswith("audit structure |")


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


def test_audit_test_quality_surfaces_new_rule__from_04fb2a(tmp_path: Path) -> None:
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
