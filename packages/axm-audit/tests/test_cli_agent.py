from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_audit_result():
    result = MagicMock()
    result.quality_score = 100
    return result


@pytest.fixture
def mock_test_report():
    report = MagicMock()
    report.failed = 0
    report.errors = 0
    return report


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


def test_cli_test_agent_prints_text(monkeypatch, capsys, tmp_path, mock_test_report):
    """test --agent prints format_audit_test_text() output, not JSON."""
    expected = "audit_test | 10 passed \u00b7 0 failed"
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *a, **kw: mock_test_report,
    )
    monkeypatch.setattr(
        "axm_audit.tools.audit_test_text.format_audit_test_text",
        lambda r: expected,
    )

    from axm_audit.cli import test

    test(str(tmp_path), agent=True)

    out = capsys.readouterr().out.strip()
    assert out.startswith("audit_test |")
    assert "{" not in out


def test_cli_test_default_prints_json(monkeypatch, capsys, tmp_path, mock_test_report):
    """test (no --agent) outputs valid JSON with the expected report fields."""
    report_dict = {"passed": 10, "failed": 0, "errors": 0}
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *a, **kw: mock_test_report,
    )
    monkeypatch.setattr("dataclasses.asdict", lambda r: report_dict)

    from axm_audit.cli import test

    test(str(tmp_path))

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["passed"] == 10
    assert data["failed"] == 0
    assert data["errors"] == 0
