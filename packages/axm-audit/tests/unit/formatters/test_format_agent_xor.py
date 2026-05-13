from __future__ import annotations

from typing import Any

import pytest

from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult, CheckResult


def _make_result(*checks: CheckResult) -> AuditResult:
    return AuditResult(checks=list(checks))


# ---------------------------------------------------------------------------
# Unit tests - text/details XOR (failed and passed-actionable buckets)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            {
                "rule_id": "R001",
                "passed": False,
                "bucket": "failed",
                "text": "• issue",
                "details": {"items": [1, 2]},
                "expected_key": "text",
                "expected_value": "• issue",
            },
            id="failed_with_text",
        ),
        pytest.param(
            {
                "rule_id": "R002",
                "passed": False,
                "bucket": "failed",
                "text": None,
                "details": {"items": [1, 2]},
                "expected_key": "details",
                "expected_value": {"items": [1, 2]},
            },
            id="failed_without_text",
        ),
        pytest.param(
            {
                "rule_id": "R003",
                "passed": True,
                "bucket": "passed",
                "text": "• item",
                "details": {"missing": ["a", "b"]},
                "expected_key": "text",
                "expected_value": "• item",
            },
            id="passed_actionable_with_text",
        ),
        pytest.param(
            {
                "rule_id": "R004",
                "passed": True,
                "bucket": "passed",
                "text": None,
                "details": {"missing": ["a", "b"]},
                "expected_key": "details",
                "expected_value": {"missing": ["a", "b"]},
            },
            id="passed_actionable_without_text",
        ),
    ],
)
def test_format_agent_text_details_xor(case: dict[str, Any]) -> None:
    cr = CheckResult(
        rule_id=case["rule_id"],
        message="msg",
        passed=case["passed"],
        text=case["text"],
        details=case["details"],
        fix_hint="fix",
    )
    out = format_agent(_make_result(cr))
    entry = out[case["bucket"]][0]
    assert isinstance(entry, dict)
    expected_key = case["expected_key"]
    other = "details" if expected_key == "text" else "text"
    assert expected_key in entry
    assert entry[expected_key] == case["expected_value"]
    assert other not in entry


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_format_agent_failed_empty_text_preserved() -> None:
    """Empty string text is falsy - falls back to details, text omitted."""
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
    assert entry["details"] == {"items": [1]}
    assert "text" not in entry


def test_format_agent_failed_both_none() -> None:
    """Both text and details None - both dropped after AXM-1410."""
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
