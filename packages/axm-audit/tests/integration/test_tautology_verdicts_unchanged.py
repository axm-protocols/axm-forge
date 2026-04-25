from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _PKG_ROOT / "tests" / "fixtures" / "tautology_verdicts_baseline.json"


def _verdict_key(v: dict[str, object]) -> tuple[object, ...]:
    return (
        v.get("file", ""),
        v.get("test", ""),
        v.get("line", 0),
        v.get("pattern", ""),
        v.get("rule", ""),
        v.get("verdict", ""),
        v.get("reason", ""),
    )


def _normalize(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        items = payload.get("verdicts", [])
    else:
        items = payload
    if not isinstance(items, list):
        return []
    return sorted(items, key=_verdict_key)


@pytest.mark.integration
def test_tautology_verdicts_unchanged() -> None:
    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=_PKG_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    current = _normalize(parsed)

    if not _FIXTURE.exists():
        _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        _FIXTURE.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    baseline = _normalize(json.loads(_FIXTURE.read_text(encoding="utf-8")))
    assert current == baseline, "tautology verdicts diverged from pre-refactor baseline"
