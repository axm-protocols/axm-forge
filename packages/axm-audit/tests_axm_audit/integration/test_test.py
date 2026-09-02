from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.test_runner import TestReport
from axm_audit.tools.audit_test import AuditTestTool


@pytest.fixture
def mock_test_report() -> TestReport:
    return TestReport(passed=10, collected=10, verdict=True)


def test_cli_test_agent_prints_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_test_report: TestReport,
) -> None:
    """The audit_test AXMTool returns its compact text rendering."""
    expected = "audit_test | 10 passed · 0 failed"
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *args, **kwargs: mock_test_report,
    )
    monkeypatch.setattr(
        "axm_audit.tools.audit_test_text.format_audit_test_text",
        lambda report: expected,
    )

    result = AuditTestTool().execute(path=str(tmp_path))

    assert result.success is True
    assert result.text == expected


def test_cli_test_default_prints_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_test_report: TestReport,
) -> None:
    """The audit_test AXMTool exposes the structured report fields."""
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *args, **kwargs: mock_test_report,
    )

    result = AuditTestTool().execute(path=str(tmp_path))

    assert isinstance(result.data, dict)
    assert result.data["passed"] == 10
    assert result.data["failed"] == 0
    assert result.data["errors"] == 0
