from __future__ import annotations

from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult, CheckResult


def _make_result(
    *checks: CheckResult, score: float = 80.0, grade: str = "B"
) -> AuditResult:
    return AuditResult(quality_score=score, grade=grade, checks=list(checks))


# ---------------------------------------------------------------------------
# Unit tests — failed checks XOR
# ---------------------------------------------------------------------------


def test_format_agent_failed_with_text() -> None:
    """Failed check with text emits text, not details."""
    cr = CheckResult(
        rule_id="R001",
        message="some failure",
        passed=False,
        text="\u2022 issue",
        details={"items": [1, 2]},
        fix_hint="fix it",
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "text" in entry
    assert entry["text"] == "\u2022 issue"
    assert "details" in entry
    assert entry["details"] == {"items": [1, 2]}


def test_format_agent_failed_without_text() -> None:
    """Failed check without text emits details, not text."""
    cr = CheckResult(
        rule_id="R002",
        message="another failure",
        passed=False,
        text=None,
        details={"items": [1, 2]},
        fix_hint="fix it",
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert entry["details"] == {"items": [1, 2]}
    assert "text" not in entry


# ---------------------------------------------------------------------------
# Unit tests — passed-with-actionable checks XOR
# ---------------------------------------------------------------------------


def test_format_agent_passed_actionable_with_text() -> None:
    """Passed actionable check with text emits text, not details."""
    cr = CheckResult(
        rule_id="R003",
        message="actionable pass",
        passed=True,
        text="\u2022 item",
        details={"missing": ["a", "b"]},
        fix_hint="add them",
    )
    out = format_agent(_make_result(cr))
    # Should be a dict (actionable), not a string
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert "text" in entry
    assert entry["text"] == "\u2022 item"
    assert "details" in entry
    assert entry["details"] == {"missing": ["a", "b"]}


def test_format_agent_passed_actionable_without_text() -> None:
    """Passed actionable check without text emits details, not text."""
    cr = CheckResult(
        rule_id="R004",
        message="actionable pass",
        passed=True,
        text=None,
        details={"missing": ["a", "b"]},
        fix_hint="add them",
    )
    out = format_agent(_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert "details" in entry
    assert entry["details"] == {"missing": ["a", "b"]}
    assert "text" not in entry


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_format_agent_failed_empty_text_treated_as_falsy() -> None:
    """Empty string text is not None — preserved after AXM-1410."""
    cr = CheckResult(
        rule_id="R005",
        message="edge empty",
        passed=False,
        text="",
        details={"items": [1]},
        fix_hint="fix",
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" in entry
    assert "text" in entry
    assert entry["text"] == ""


def test_format_agent_failed_both_none() -> None:
    """Both text and details None — both dropped after AXM-1410."""
    cr = CheckResult(
        rule_id="R006",
        message="both none",
        passed=False,
        text=None,
        details=None,
        fix_hint="fix",
    )
    out = format_agent(_make_result(cr))
    entry = out["failed"][0]
    assert "details" not in entry
    assert "text" not in entry
    assert set(entry.keys()) == {"rule_id", "message", "fix_hint"}
