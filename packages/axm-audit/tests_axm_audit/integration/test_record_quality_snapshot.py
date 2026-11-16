"""Record an exported revision using its explicit source identity."""

import json
from pathlib import Path

import pytest
from axm_ingot import QualityOrigin

from axm_audit import quality_trace
from axm_audit.tools.audit import AuditTool

pytestmark = pytest.mark.integration


def test_export_measurement_records_dev_origin(tmp_path: Path, monkeypatch) -> None:
    history = tmp_path / "history"
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: history)
    snapshot = tmp_path / "export" / "temporary-package"
    snapshot.mkdir(parents=True)
    source = tmp_path.resolve() / "source" / "packages" / "demo"
    origin = {"path": str(source), "sha": "a" * 40, "branch": "dev"}

    result = AuditTool().execute(
        path=str(snapshot), category="structure", snapshot_origin=origin
    )

    assert result.data["snapshot_recorded"] is True
    rows = [
        json.loads(line) for line in (history / "demo.jsonl").read_text().splitlines()
    ]
    assert [row["kind"] for row in rows] == ["audit", "code"]
    for row in rows:
        assert row["repo"] == "demo"
        assert row["source_path"] == str(source)
        assert row["sha"] == "a" * 40
        assert row["branch"] == "dev"
    assert not (history / "temporary-package.jsonl").exists()


def test_write_failure_reports_false_without_losing_measurement(
    tmp_path: Path, monkeypatch
) -> None:
    destination = tmp_path / "not-a-directory"
    destination.write_text("occupied")
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: destination)
    origin = QualityOrigin(tmp_path.resolve() / "source" / "demo", "b" * 40, "dev")
    assert (
        quality_trace.record_quality_snapshot(
            path=str(tmp_path),
            kind="audit",
            data={"score": 50, "grade": "F", "failed": []},
            origin=origin,
        )
        is False
    )

    result = AuditTool().execute(
        path=str(tmp_path),
        category="structure",
        snapshot_origin={
            "path": str(origin.path),
            "sha": origin.sha,
            "branch": origin.branch,
        },
    )
    assert result.data["snapshot_recorded"] is False
    assert "score" in result.data
