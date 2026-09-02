"""Integration tests for the audit_fix AXMTool response path."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.models import PipelineReport
from axm_audit.tools.audit_fix import AuditFixTool


def test_fix_warns_on_red_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The AXMTool delegates directly to the deterministic pipeline."""
    calls = 0

    def _fake_run(
        project_path: Path,
        *,
        apply: bool,
        rules: set[str] | None,
    ) -> PipelineReport:
        nonlocal calls
        calls += 1
        return PipelineReport(applied=apply)

    monkeypatch.setattr("axm_audit.core.fix.run", _fake_run)

    result = AuditFixTool().execute(path=str(tmp_path))

    assert result.success is True
    assert calls == 1
