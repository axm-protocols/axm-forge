from __future__ import annotations

from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult, CheckResult


def _make_result(
    *checks: CheckResult, score: float = 80.0, grade: str = "B"
) -> AuditResult:
    return AuditResult(quality_score=score, grade=grade, checks=list(checks))


# ---------------------------------------------------------------------------
# Unit tests — from test_spec
# ---------------------------------------------------------------------------


def test_format_agent_failed_text_excludes_details() -> None:
    """When failed check has text, emit text only — details omitted."""
    cr = CheckResult(
        rule_id="R001",
        message="failure",
        passed=False,
        text="\u2022 issue",
        details={"items": [1]},
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "text" in entry
    assert entry["text"] == "\u2022 issue"
    assert "details" not in entry


def test_format_agent_failed_no_text_includes_details() -> None:
    """When failed check has text=None, emit details as fallback."""
    cr = CheckResult(
        rule_id="R002",
        message="failure",
        passed=False,
        text=None,
        details={"items": [1]},
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert entry["details"] == {"items": [1]}
    assert "text" not in entry


def test_format_agent_failed_empty_text_falls_back() -> None:
    """When failed check has text='', treat as falsy — emit details."""
    cr = CheckResult(
        rule_id="R003",
        message="failure",
        passed=False,
        text="",
        details={"items": [1]},
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert entry["details"] == {"items": [1]}
    assert "text" not in entry


# ---------------------------------------------------------------------------
# Edge cases — from test_spec
# ---------------------------------------------------------------------------


def test_format_agent_failed_both_none() -> None:
    """Both text=None and details=None — neither key in output."""
    cr = CheckResult(
        rule_id="R010",
        message="both none",
        passed=False,
        text=None,
        details=None,
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "text" not in entry
    assert "details" not in entry


def test_format_agent_failed_text_only_no_details() -> None:
    """text present, details=None — only text in output."""
    cr = CheckResult(
        rule_id="R011",
        message="text only",
        passed=False,
        text="\u2022 issue",
        details=None,
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "text" in entry
    assert entry["text"] == "\u2022 issue"
    assert "details" not in entry


def test_format_agent_failed_empty_details_dict() -> None:
    """text=None, details={} — details present (empty dict is not None)."""
    cr = CheckResult(
        rule_id="R012",
        message="empty details",
        passed=False,
        text=None,
        details={},
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert entry["details"] == {}
    assert "text" not in entry
