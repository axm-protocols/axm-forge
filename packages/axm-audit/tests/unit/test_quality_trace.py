"""Unit tests for the quality-snapshot helpers (no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit import quality_trace
from axm_audit.quality_trace import normalize_fails, record_quality_snapshot


def test_normalize_fails_audit_shape() -> None:
    """Audit ``failed`` entries map to {rule_id, message, fix_hint}."""
    data = {
        "failed": [
            {"rule_id": "QUALITY_LINT", "message": "5 issues", "fix_hint": "ruff --fix"}
        ]
    }
    assert normalize_fails(data) == [
        {"rule_id": "QUALITY_LINT", "message": "5 issues", "fix_hint": "ruff --fix"}
    ]


def test_normalize_fails_governance_shape() -> None:
    """Init ``failures`` use name/fix → normalized to rule_id/fix_hint."""
    data = {
        "failures": [{"name": "structure.src", "message": "no src/", "fix": "mkdir"}]
    }
    assert normalize_fails(data) == [
        {"rule_id": "structure.src", "message": "no src/", "fix_hint": "mkdir"}
    ]


def test_normalize_fails_missing_key_returns_empty() -> None:
    """A payload without failed/failures yields no fails."""
    assert normalize_fails({"score": 100}) == []


def test_record_never_raises_on_bad_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing target directory is swallowed, never propagated (no I/O)."""

    def _boom() -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(quality_trace, "_quality_dir", _boom)
    # Must not raise — observability never breaks an audit.
    record_quality_snapshot(path=".", kind="audit", data={"score": 100})
