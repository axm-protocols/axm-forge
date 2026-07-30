from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.formatters import (
    format_test_quality_text,
)

pytestmark = pytest.mark.integration

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "snapshots" / "formatters"
)


def _assert_snapshot(name: str, actual: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / name
    if not path.exists():
        path.write_text(actual + "\n" if not actual.endswith("\n") else actual)
    expected = path.read_text().rstrip("\n")
    assert actual.rstrip("\n") == expected, f"Snapshot drift for {name}"


def test_format_test_quality_text_snapshot_stable(audit_result: Any) -> None:
    actual = format_test_quality_text(audit_result)
    _assert_snapshot("format_test_quality_text.txt", actual)
