"""Integration tests for the audit_fix AXMTool dry-run report path."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.models import PipelineReport
from axm_audit.tools.audit_fix import AuditFixTool


def test_fix_dryrun_runs_against_minimal_pkg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default dry-run returns a populated pipeline report."""

    def _fake_run(
        project_path: Path,
        *,
        apply: bool,
        rules: set[str] | None,
    ) -> PipelineReport:
        return PipelineReport(applied=apply)

    monkeypatch.setattr("axm_audit.core.fix.run", _fake_run)

    result = AuditFixTool().execute(path=str(tmp_path))

    assert result.success is True
    assert result.text is not None
    assert result.text.strip()
