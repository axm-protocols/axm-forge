from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.tools.audit import AuditTool


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
