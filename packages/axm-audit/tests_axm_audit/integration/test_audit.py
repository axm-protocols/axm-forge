"""Integration tests for the audit AXMTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.models.results import AuditResult, CheckResult
from axm_audit.tools.audit import AuditTool


def _result(project: Path, *, score: int, passed: bool) -> AuditResult:
    return AuditResult(
        project_path=str(project),
        checks=[
            CheckResult(
                rule_id="QUALITY_LINT",
                passed=passed,
                message="ok" if passed else "bad",
                text=None if passed else "some text",
                fix_hint=None if passed else "run ruff",
                category="lint",
                score=score,
            )
        ],
    )


def test_audit_agent_output_runs_through_formatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The AXMTool returns the compact agent rendering."""
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *args, **kwargs: _result(tmp_path, score=100, passed=True),
    )

    result = AuditTool().execute(path=str(tmp_path))

    assert result.success is True
    assert result.text is not None
    assert "audit" in result.text.lower()


def test_audit_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The AXMTool exposes the structured audit payload."""
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *args, **kwargs: _result(tmp_path, score=100, passed=True),
    )

    result = AuditTool().execute(path=str(tmp_path))

    assert isinstance(result.data, dict)
    assert result.data["score"] == 100


def test_audit_exits_when_score_below_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A low score remains visible in the AXMTool response."""
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *args, **kwargs: _result(tmp_path, score=10, passed=False),
    )

    result = AuditTool().execute(path=str(tmp_path))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["score"] == 10
    assert result.data["failed"]
