"""Integration tests for the ``test-quality`` CLI command (in-process)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.cli import test_quality as cli_test_quality


def test_test_quality_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test-quality --json` emits structured JSON output."""
    fake_result = MagicMock(
        checks=[],
        quality_score=100,
        grade="A",
        project_path=str(tmp_path),
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    project = tmp_path / "proj_tq_json"
    project.mkdir()
    cli_test_quality(path=str(project), json_output=True)
    out = capsys.readouterr().out
    json.loads(out)
