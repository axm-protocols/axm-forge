from __future__ import annotations

from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult, CheckResult


def _make_result(checks: list[CheckResult]) -> AuditResult:
    return AuditResult(quality_score=80.0, grade="B", checks=checks)


# --- Unit tests ---


def test_format_agent_failed_with_text_includes_both() -> None:
    """When a failed check has text and details, only text is emitted."""
    check = CheckResult(
        rule_id="R001",
        message="some issue",
        passed=False,
        text="\u2022 file:1: issue",
        details={"locations": ["file:1"]},
        fix_hint="fix it",
    )
    out = format_agent(_make_result([check]))
    failed = out["failed"]
    assert len(failed) == 1
    assert failed[0]["text"] == "\u2022 file:1: issue"
    assert "details" not in failed[0]


def test_format_agent_failed_without_text_includes_details() -> None:
    """When a failed check has text=None, details key must be present."""
    check = CheckResult(
        rule_id="R002",
        message="another issue",
        passed=False,
        text=None,
        details={"locations": ["file:2"]},
        fix_hint=None,
    )
    out = format_agent(_make_result([check]))
    failed = out["failed"]
    assert len(failed) == 1
    assert "details" in failed[0]
    assert failed[0]["details"] == {"locations": ["file:2"]}


def test_format_agent_passed_actionable_unchanged() -> None:
    """Passed checks with actionable detail still include details."""
    check = CheckResult(
        rule_id="R003",
        message="missing docstrings",
        passed=True,
        text=None,
        details={"missing": ["foo", "bar"]},
        fix_hint=None,
    )
    out = format_agent(_make_result([check]))
    # Should be promoted to dict with details
    passed_dicts = [p for p in out["passed"] if isinstance(p, dict)]
    assert len(passed_dicts) == 1
    assert "details" in passed_dicts[0]
    assert passed_dicts[0]["details"] == {"missing": ["foo", "bar"]}


# --- Edge cases ---


def test_format_agent_failed_empty_text_excluded() -> None:
    """Empty string text is falsy — details present, text absent."""
    check = CheckResult(
        rule_id="R004",
        message="edge case",
        passed=False,
        text="",
        details={"issues": ["a"]},
        fix_hint=None,
    )
    out = format_agent(_make_result([check]))
    failed = out["failed"]
    assert len(failed) == 1
    assert "details" in failed[0]
    assert failed[0]["details"] == {"issues": ["a"]}
    assert "text" not in failed[0]


def test_format_agent_failed_both_none_no_crash() -> None:
    """Both text and details None — must not crash."""
    check = CheckResult(
        rule_id="R005",
        message="both none",
        passed=False,
        text=None,
        details=None,
        fix_hint=None,
    )
    out = format_agent(_make_result([check]))
    failed = out["failed"]
    assert len(failed) == 1
    # details is None so filtered out by the v is not None guard
    assert failed[0]["rule_id"] == "R005"
