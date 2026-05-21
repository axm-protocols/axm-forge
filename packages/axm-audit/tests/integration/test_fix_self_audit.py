"""AC9: audit_fix tool wires AuditFixTool → core.fix.pipeline.run cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.tools.audit_fix import AuditFixTool

pytestmark = pytest.mark.integration


def test_audit_fix_dry_run_on_self_is_clean(tmp_path: Path) -> None:
    """AC9: audit_fix dry-run plans zero ops on an empty project.

    Sanity check that the dispatcher (AuditFixTool.execute →
    core.fix.pipeline.run → format_report) wires up correctly and returns
    a ``data["ops"] == []`` empty plan when the input tree has no test
    files to relocate / rename / split.
    """
    tool = AuditFixTool()
    result = tool.execute(path=str(tmp_path), apply=False)

    assert result.success, result.error
    assert result.data is not None
    assert result.data["ops"] == []
