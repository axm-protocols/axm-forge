"""Split from ``test_cli_agent.py``."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_audit_result():
    result = MagicMock()
    result.quality_score = 100
    return result


def test_cli_audit_agent_prints_text(monkeypatch, capsys, tmp_path, mock_audit_result):
    """audit --agent prints format_agent_text() output, not JSON."""
    expected = "audit | A 100 | 5 pass \u00b7 0 fail"
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *a, **kw: mock_audit_result,
    )
    monkeypatch.setattr(
        "axm_audit.cli.format_agent",
        lambda r: {"score": 100, "grade": "A", "passed": [], "failed": []},
    )
    monkeypatch.setattr(
        "axm_audit.cli.format_agent_text",
        lambda data, category=None: expected,
    )

    from axm_audit.cli import audit

    audit(str(tmp_path), agent=True)

    out = capsys.readouterr().out.strip()
    assert out.startswith("audit |")
    assert "{" not in out


def test_cli_audit_json_unchanged(monkeypatch, capsys, tmp_path, mock_audit_result):
    """audit --json still outputs valid JSON with score key."""
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *a, **kw: mock_audit_result,
    )
    monkeypatch.setattr(
        "axm_audit.cli.format_json",
        lambda r: {"score": 100, "grade": "A"},
    )

    from axm_audit.cli import audit

    audit(str(tmp_path), json_output=True)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert "score" in data
