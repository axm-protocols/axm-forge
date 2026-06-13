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
