"""Integration tests for ``record_quality_snapshot`` (real file I/O)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_init import quality_trace
from axm_init.quality_trace import record_quality_snapshot

pytestmark = pytest.mark.integration


def test_record_appends_governance_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A governance snapshot is appended as one JSON line."""
    monkeypatch.setattr(quality_trace, "_quality_dir", lambda: tmp_path)
    record_quality_snapshot(
        path=str(tmp_path),
        kind="governance",
        data={"score": 100, "grade": "A", "failures": []},
    )
    written = (tmp_path / f"{tmp_path.name}.jsonl").read_text().splitlines()
    assert len(written) == 1
    line = json.loads(written[0])
    assert line["kind"] == "governance"
    assert line["score"] == 100
