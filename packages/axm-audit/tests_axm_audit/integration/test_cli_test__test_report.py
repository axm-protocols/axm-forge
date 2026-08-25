"""Integration tests for the ``test`` CLI command rendering a TestReport."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit.cli import test as cli_test


def test_test_cli_agent_renders_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test --agent` formats via format_audit_test_text."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test"
    project.mkdir()
    report = TestReport(passed=3, failed=0, errors=0, skipped=0, duration=0.1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    cli_test(path=str(project), agent=True)
    out = capsys.readouterr().out
    assert "audit_test |" in out
    assert "3 passed" in out


def test_test_cli_default_emits_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``--agent``, `test` emits a JSON dataclass dump."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test_json"
    project.mkdir()
    report = TestReport(passed=1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    cli_test(path=str(project), agent=False)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["passed"] == 1


def test_test_cli_failure_exits_with_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test` exits 1 when the report has any failures/errors."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test_fail"
    project.mkdir()
    report = TestReport(passed=0, failed=1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    with pytest.raises(SystemExit) as excinfo:
        cli_test(path=str(project), agent=False)
    assert excinfo.value.code == 1
    capsys.readouterr()
