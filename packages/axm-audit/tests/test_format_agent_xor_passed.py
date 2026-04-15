from __future__ import annotations

from axm_audit.formatters import format_agent
from axm_audit.models.results import AuditResult, CheckResult


def _make_result(*checks: CheckResult) -> AuditResult:
    return AuditResult(checks=list(checks), quality_score=100, grade="A")


# ── Unit tests ──────────────────────────────────────────────────────


def test_format_agent_passed_actionable_text_excludes_details() -> None:
    """Passed check with truthy text should emit text only, not details."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text="\u2022 item",
        details={"missing": ["a"]},
    )
    out = format_agent(_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["text"] == "\u2022 item"
    assert "details" not in entry


def test_format_agent_passed_actionable_no_text_includes_details() -> None:
    """Passed check with text=None should emit details as fallback."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text=None,
        details={"missing": ["a"]},
    )
    out = format_agent(_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["details"] == {"missing": ["a"]}
    assert "text" not in entry


# ── Edge cases ──────────────────────────────────────────────────────


def test_format_agent_passed_actionable_empty_text_uses_details() -> None:
    """Empty string text is falsy — should emit details, not text."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="ok",
        text="",
        details={"missing": ["a"]},
    )
    out = format_agent(_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert "details" in entry
    assert "text" not in entry


def test_format_agent_passed_non_actionable_string_form() -> None:
    """Passed check with text but no actionable details stays as string."""
    cr = CheckResult(
        rule_id="R1",
        passed=True,
        message="info",
        text="\u2022 info",
        details=None,
    )
    out = format_agent(_make_result(cr))
    entry = out["passed"][0]
    assert isinstance(entry, str)
    assert "R1" in entry
