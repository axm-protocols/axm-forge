"""Split from ``test_formatters_snapshots.py``."""

from pathlib import Path
from typing import Any

from axm_audit.formatters import format_agent, format_agent_text

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


def test_format_agent_text_snapshot_stable(audit_result: Any) -> None:
    data = format_agent(audit_result)
    actual = format_agent_text(data, category="quality")
    _assert_snapshot("format_agent_text.txt", actual)
