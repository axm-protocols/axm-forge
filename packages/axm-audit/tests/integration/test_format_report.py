"""Split from ``test_formatters_snapshots.py``."""

from pathlib import Path
from typing import Any

from axm_audit.formatters import format_report

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


def test_format_report_snapshot_stable(audit_result: Any) -> None:
    actual = format_report(audit_result)
    _assert_snapshot("format_report.txt", actual)
