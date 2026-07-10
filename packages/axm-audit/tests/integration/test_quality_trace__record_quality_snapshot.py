"""Integration tests for ``record_quality_snapshot`` (real file I/O)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit import quality_trace
from axm_audit.quality_trace import record_quality_snapshot

pytestmark = pytest.mark.integration


def test_record_appends_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot is appended as one JSON line with the expected fields."""
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: tmp_path)
    record_quality_snapshot(
        path=str(tmp_path),
        kind="audit",
        data={"score": 97.5, "grade": "A", "failed": []},
    )
    written = (tmp_path / f"{tmp_path.name}.jsonl").read_text().splitlines()
    assert len(written) == 1
    line = json.loads(written[0])
    assert line["kind"] == "audit"
    assert line["score"] == 97.5
    assert line["grade"] == "A"
    assert "ts" in line


def test_record_is_append_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two runs produce two lines (history, not overwrite)."""
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: tmp_path)
    for _ in range(2):
        record_quality_snapshot(
            path=str(tmp_path), kind="audit", data={"score": 1, "grade": "F"}
        )
    written = (tmp_path / f"{tmp_path.name}.jsonl").read_text().splitlines()
    assert len(written) == 2


def test_code_kind_writes_metrics_not_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kind='code' line carries lines/modules/... and omits score/grade/fails."""
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: tmp_path)
    monkeypatch.setattr(quality_trace, "_git_head", lambda _p: ("abc1234", "main"))
    record_quality_snapshot(
        path=str(tmp_path / "pkg"),
        kind="code",
        data={"lines": 900, "modules": 10, "functions": 19, "classes": 9},
    )
    line = json.loads((tmp_path / "pkg.jsonl").read_text(encoding="utf-8").strip())
    assert line["kind"] == "code"
    assert line["lines"] == 900
    assert line["modules"] == 10
    assert "score" not in line
    assert "fails" not in line
