from __future__ import annotations

from typing import Any

import pytest

from axm_audit.formatters import format_agent, format_agent_text
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


# ---------------------------------------------------------------------------
# format_agent_text — Unit tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_audit_data() -> dict[str, Any]:
    """3 passed strings + 1 failed dict with text."""
    return {
        "score": 85,
        "grade": "B",
        "passed": [
            "QUALITY_LINT: Lint score: 100/100 (0 issues)",
            "QUALITY_TYPES: Type coverage OK",
            "QUALITY_SECURITY: No issues found",
        ],
        "failed": [
            {
                "rule_id": "QUALITY_COMPLEXITY",
                "message": "3 functions exceed CC threshold",
                "text": "src/mod.py:10 func_a CC=15\nsrc/mod.py:30 func_b CC=12",
                "fix_hint": "Extract helpers to reduce CC",
            },
        ],
    }


def test_format_agent_text_full_audit(full_audit_data: dict[str, Any]) -> None:
    text = format_agent_text(full_audit_data)
    lines = text.splitlines()

    # Header
    header = lines[0]
    assert "3 pass" in header
    assert "1 fail" in header

    # Passed section — all 3 rule_ids on ✓ line(s)
    assert "QUALITY_LINT" in text
    assert "QUALITY_TYPES" in text
    assert "QUALITY_SECURITY" in text
    assert "✓" in text

    # Failed section — detail present
    assert "QUALITY_COMPLEXITY" in text
    assert "✗" in text
    assert "3 functions exceed CC threshold" in text
    assert "src/mod.py:10 func_a CC=15" in text
    assert "Extract helpers to reduce CC" in text


def test_format_agent_text_category_all_pass() -> None:
    data = {
        "score": 100,
        "grade": "A",
        "passed": [
            "QUALITY_LINT: Lint score: 100/100 (0 issues)",
            "QUALITY_STYLE: Style OK",
        ],
        "failed": [],
    }
    text = format_agent_text(data, category="lint")
    assert text.startswith("audit lint")
    assert "2 pass" in text
    assert "0 fail" in text
    assert "✗" not in text


def test_format_agent_text_category_all_fail() -> None:
    data = {
        "score": 0,
        "grade": "F",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_TYPES",
                "message": "Type errors found",
                "text": "src/a.py:1 error: Missing return type",
            },
        ],
    }
    text = format_agent_text(data, category="type")
    assert text.startswith("audit type")
    assert "0 pass" in text
    assert "1 fail" in text
    assert "✓" not in text


def test_format_agent_text_none_score() -> None:
    data = {
        "score": None,
        "grade": None,
        "passed": ["STRUCT_LAYOUT: OK"],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "None" not in text
    assert "1 pass" in text


def test_format_agent_text_actionable_passed() -> None:
    data = {
        "score": 90,
        "grade": "A",
        "passed": [
            {
                "rule_id": "QUALITY_DOCS",
                "message": "Docstring coverage 80%",
                "details": {"missing": ["src/a.py::foo"]},
            },
        ],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "QUALITY_DOCS" in text
    assert "✓" in text


def test_format_agent_text_failed_no_text_uses_details() -> None:
    data = {
        "score": 50,
        "grade": "D",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_SECURITY",
                "message": "Security issues found",
                "details": {"issues": ["S101 assert used", "S105 hardcoded password"]},
            },
        ],
    }
    text = format_agent_text(data)
    assert "QUALITY_SECURITY" in text
    assert "issues" in text


# ---------------------------------------------------------------------------
# format_agent_text — Edge cases
# ---------------------------------------------------------------------------


def test_format_agent_text_empty_checks() -> None:
    data: dict[str, Any] = {
        "score": None,
        "grade": None,
        "passed": [],
        "failed": [],
    }
    text = format_agent_text(data)
    assert "0 pass" in text
    assert "0 fail" in text


def test_format_agent_text_long_passed_list() -> None:
    passed = [f"RULE_{i:02d}: Check {i} passed" for i in range(22)]
    data = {
        "score": 95,
        "grade": "A",
        "passed": passed,
        "failed": [],
    }
    text = format_agent_text(data)
    # Passed should be grouped into lines of ≤5 rule_ids each
    check_lines = [ln for ln in text.splitlines() if "✓" in ln]
    for ln in check_lines:
        rule_ids = [tok for tok in ln.split() if tok.startswith("RULE_")]
        assert len(rule_ids) <= 5
    assert "22 pass" in text


def test_format_agent_text_failed_no_fix_hint() -> None:
    data = {
        "score": 60,
        "grade": "C",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_TESTS",
                "message": "Coverage below threshold",
                "text": "Coverage: 45%",
            },
        ],
    }
    text = format_agent_text(data)
    assert "QUALITY_TESTS" in text
    # No fix: line emitted
    assert "fix:" not in text.lower()


def test_format_agent_text_failed_multiline_text() -> None:
    multiline = "\n".join(f"src/file{i}.py:1 error {i}" for i in range(6))
    data = {
        "score": 30,
        "grade": "F",
        "passed": [],
        "failed": [
            {
                "rule_id": "QUALITY_LINT",
                "message": "Many lint errors",
                "text": multiline,
                "fix_hint": "Run ruff --fix",
            },
        ],
    }
    text = format_agent_text(data)
    for i in range(6):
        assert f"src/file{i}.py:1 error {i}" in text
