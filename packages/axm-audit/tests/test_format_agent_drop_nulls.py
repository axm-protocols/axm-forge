from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from axm_audit.formatters import format_agent


@dataclass
class _CheckResult:
    rule_id: str
    message: str
    passed: bool
    text: str | None = None
    details: dict[str, Any] | None = None
    fix_hint: str | None = None


@dataclass
class _AuditResult:
    quality_score: int = 100
    grade: str = "A"
    checks: list[_CheckResult] = field(default_factory=list)


# ── Unit tests ──────────────────────────────────────────────────────


def test_format_agent_drops_null_keys_failed() -> None:
    """Failed dict with all nullable fields None has only rule_id + message."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R001",
                message="something failed",
                passed=False,
                details=None,
                text=None,
                fix_hint=None,
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    failed = output["failed"]
    assert len(failed) == 1
    assert set(failed[0].keys()) == {"rule_id", "message"}


def test_format_agent_keeps_non_null_keys_failed() -> None:
    """Failed dict with text and details — only text emitted (XOR)."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R002",
                message="check failed",
                passed=False,
                details={"score": 50},
                text="\u2022 issue",
                fix_hint="fix it",
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    failed = output["failed"]
    assert len(failed) == 1
    assert set(failed[0].keys()) == {
        "rule_id",
        "message",
        "text",
        "fix_hint",
    }


def test_format_agent_drops_null_fix_hint_passed() -> None:
    """Passed actionable dict with fix_hint=None omits fix_hint key."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R003",
                message="has missing items",
                passed=True,
                details={"missing": ["x"]},
                fix_hint=None,
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    passed = output["passed"]
    assert len(passed) == 1
    assert isinstance(passed[0], dict)
    assert "fix_hint" not in passed[0]


# ── Edge cases ──────────────────────────────────────────────────────


def test_format_agent_all_keys_present_failed() -> None:
    """When all fields are populated, text wins — details excluded (XOR)."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R010",
                message="full check",
                passed=False,
                text="detail text",
                details={"score": 80},
                fix_hint="try this",
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    failed = output["failed"]
    assert set(failed[0].keys()) == {
        "rule_id",
        "message",
        "text",
        "fix_hint",
    }


def test_format_agent_only_nullables_null_failed() -> None:
    """Failed dict with all nullable fields None yields only rule_id + message."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R011",
                message="minimal",
                passed=False,
                details=None,
                text=None,
                fix_hint=None,
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    failed = output["failed"]
    assert set(failed[0].keys()) == {"rule_id", "message"}


def test_format_agent_mixed_nulls_failed() -> None:
    """Failed dict with text=None but details and fix_hint present has 4 keys."""
    result = _AuditResult(
        checks=[
            _CheckResult(
                rule_id="R012",
                message="mixed",
                passed=False,
                text=None,
                details={"issues": ["a"]},
                fix_hint="do something",
            ),
        ],
    )
    output = format_agent(result)  # type: ignore[arg-type]
    failed = output["failed"]
    assert set(failed[0].keys()) == {"rule_id", "message", "details", "fix_hint"}
    assert "text" not in failed[0]
