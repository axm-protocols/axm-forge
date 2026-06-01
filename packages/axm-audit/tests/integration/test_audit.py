"""Integration tests for the ``audit`` CLI command (in-process invocation)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.cli import audit


def test_audit_agent_output_runs_through_formatter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit --agent` exercises the agent formatter on a stubbed result."""
    pkg = tmp_path / "proj"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    fake_result = MagicMock(
        checks=[
            MagicMock(
                passed=True,
                rule_id="QUALITY_LINT",
                message="ok",
                text=None,
                details=None,
                fix_hint=None,
            )
        ],
        quality_score=100,
        grade="A",
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    audit(path=str(pkg), agent=True)
    out = capsys.readouterr().out
    assert "audit" in out.lower()


def test_audit_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit --json` emits valid JSON to stdout."""
    pkg = tmp_path / "proj_json"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *a, **kw: MagicMock(quality_score=100),
    )
    monkeypatch.setattr(
        "axm_audit.cli.format_json",
        lambda result: {"score": 100, "checks": []},
    )
    audit(path=str(pkg), json_output=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["score"] == 100


def test_audit_exits_when_score_below_threshold(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit` exits 1 when ``quality_score`` is below PASS_THRESHOLD."""
    pkg = tmp_path / "proj_fail"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    fake_result = MagicMock(
        checks=[
            MagicMock(
                passed=False,
                rule_id="QUALITY_LINT",
                message="bad",
                text="some text",
                details=None,
                fix_hint="run ruff",
                category="lint",
                score=10,
                metadata=None,
            )
        ],
        quality_score=10,
        grade="F",
        project_path=str(pkg),
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    with pytest.raises(SystemExit) as excinfo:
        audit(path=str(pkg))
    assert excinfo.value.code == 1
    capsys.readouterr()  # drain
