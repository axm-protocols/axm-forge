"""Unit tests for the quality-snapshot helpers (no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init import quality_trace
from axm_init.quality_trace import normalize_fails, record_quality_snapshot


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            {
                "failures": [
                    {"name": "structure.src", "message": "no src/", "fix": "mkdir"}
                ]
            },
            [{"rule_id": "structure.src", "message": "no src/", "fix_hint": "mkdir"}],
            id="governance_shape",
        ),
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
        pytest.param({"score": 100}, [], id="missing_key_returns_empty"),
    ],
)
def test_normalize_fails(
    data: dict[str, object], expected: list[dict[str, str]]
) -> None:
    """Governance/audit shapes normalize to {rule_id, message, fix_hint}; else empty."""
    assert normalize_fails(data) == expected


def test_record_never_raises_on_bad_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing target directory is swallowed, never propagated (no I/O)."""

    def _boom() -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(quality_trace, "_quality_dir", _boom)
    record_quality_snapshot(path=".", kind="governance", data={"score": 100})
