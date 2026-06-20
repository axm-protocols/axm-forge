"""Unit tests for the quality-snapshot helpers (no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit import quality_trace
from axm_audit.quality_trace import normalize_fails, record_quality_snapshot


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            {
                "failed": [
                    {
                        "rule_id": "QUALITY_LINT",
                        "message": "5 issues",
                        "fix_hint": "ruff --fix",
                    }
                ]
            },
            [
                {
                    "rule_id": "QUALITY_LINT",
                    "message": "5 issues",
                    "fix_hint": "ruff --fix",
                }
            ],
            id="audit_shape",
        ),
        pytest.param(
            {
                "failures": [
                    {"name": "structure.src", "message": "no src/", "fix": "mkdir"}
                ]
            },
            [{"rule_id": "structure.src", "message": "no src/", "fix_hint": "mkdir"}],
            id="governance_shape",
        ),
        pytest.param({"score": 100}, [], id="missing_key_returns_empty"),
    ],
)
def test_normalize_fails_maps_payload_shapes(
    data: dict[str, object], expected: list[dict[str, str]]
) -> None:
    """normalize_fails maps audit/governance shapes and empties unknown payloads."""
    assert normalize_fails(data) == expected


def test_record_never_raises_on_bad_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing target directory is swallowed, never propagated (no I/O)."""

    def _boom() -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(quality_trace, "_quality_dir", _boom)
    # Must not raise — observability never breaks an audit.
    record_quality_snapshot(path=".", kind="audit", data={"score": 100})


def test_code_kind_writes_metrics_not_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kind='code' line carries lines/modules/... and omits score/grade/fails."""
    import json

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
