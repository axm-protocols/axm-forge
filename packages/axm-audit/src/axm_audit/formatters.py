"""Output formatters for audit results — human-readable and JSON."""

from __future__ import annotations

import logging
from typing import Any

from axm_audit.core.rules.base import PERFECT_SCORE
from axm_audit.models.results import AuditResult, CheckResult

logger = logging.getLogger(__name__)

_GRADE_EMOJI = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}


def _format_check_details(check: CheckResult) -> list[str]:
    """Extract contextual detail lines from a check result.

    Returns the pre-rendered ``text`` lines when available.
    Returns empty list for checks without text.
    """
    if check.text:
        return check.text.splitlines()
    return []


# ── Report section formatters ────────────────────────────────────────


def _format_categories(result: AuditResult) -> list[str]:
    """Format category breakdown section."""
    groups: dict[str, list[CheckResult]] = {}
    for check in result.checks:
        cat = check.category or "other"
        groups.setdefault(cat, []).append(check)

    lines: list[str] = []
    for cat_name, checks in groups.items():
        lines.append(f"  {cat_name}")
        for check in checks:
            status = "✅" if check.passed else "❌"
            lines.append(f"    {status} {check.rule_id:<30s}  {check.message}")
        lines.append("")
    return lines


def _format_score(result: AuditResult) -> list[str]:
    """Format score and grade section."""
    lines: list[str] = []
    if result.quality_score is not None:
        emoji = _GRADE_EMOJI.get(result.grade or "", "")
        lines.append(
            f"  Score: {result.quality_score}/100 — Grade {result.grade} {emoji}"
        )
    lines.append("")
    return lines


def _is_improvable(check: CheckResult) -> bool:
    """Return True if check passed but scored below 100."""
    if not check.passed or not check.details:
        return False
    score = check.details.get("score")
    return score is not None and score < PERFECT_SCORE


def _format_one_improvement(check: CheckResult) -> list[str]:
    """Format a single improvement entry."""
    score = check.details["score"] if check.details else "?"
    lines = [f"  ⚡ {check.rule_id} ({score}/100)"]
    lines.extend(_format_check_details(check))
    if check.fix_hint:
        lines.append(f"     Tip: {check.fix_hint}")
    lines.append("")
    return lines


def _format_improvements(result: AuditResult) -> list[str]:
    """Format improvements section for passing checks with score < 100."""
    improvable = [c for c in result.checks if _is_improvable(c)]
    if not improvable:
        return []

    lines: list[str] = [f"  ⚠️  Improvements ({len(improvable)}):", ""]
    for check in improvable:
        lines.extend(_format_one_improvement(check))
        lines.append("")
    return lines


def _format_failures(result: AuditResult) -> list[str]:
    """Format failure section with contextual details."""
    failed = [c for c in result.checks if not c.passed]
    if not failed:
        return []

    lines: list[str] = []
    lines.append(f"  📝 Failures ({len(failed)}):")
    lines.append("")
    for check in failed:
        lines.append(f"  ❌ {check.rule_id}")
        lines.append(f"     Problem: {check.message}")
        for detail in _format_check_details(check):
            lines.append(detail)
        if check.fix_hint:
            lines.append(f"     Fix:     {check.fix_hint}")
        lines.append("")
    return lines


def format_report(result: AuditResult) -> str:
    """Format audit result as human-readable category-grouped report."""
    lines: list[str] = [
        "📋 axm-audit — Quality Audit",
        f"   Path: {result.project_path or 'unknown'}",
        "",
    ]
    lines.extend(_format_categories(result))
    lines.extend(_format_score(result))
    lines.extend(_format_improvements(result))
    lines.extend(_format_failures(result))
    return "\n".join(lines)


def format_json(result: AuditResult) -> dict[str, Any]:
    """Format audit result as JSON-serializable dict."""
    return {
        "score": result.quality_score,
        "grade": result.grade,
        "total": result.total,
        "failed": result.failed,
        "success": result.success,
        "checks": [
            {
                "rule_id": c.rule_id,
                "passed": c.passed,
                "message": c.message,
                "details": c.details,
            }
            for c in result.checks
        ],
    }


def format_agent(result: AuditResult) -> dict[str, Any]:
    """Agent-optimized output: passed=summary, failed=full detail.

    Minimizes tokens for passing checks while giving full context on
    failures.  Passed checks that carry actionable detail (e.g. missing
    docstrings) include a ``details`` dict so the agent can act on them.
    """
    passed: list[str | dict[str, Any]] = []
    for c in result.checks:
        if not c.passed:
            continue
        if _has_actionable_detail(c):
            passed.append(
                {
                    "rule_id": c.rule_id,
                    "message": c.message,
                    "details": c.details,
                    "fix_hint": c.fix_hint,
                }
            )
        else:
            passed.append(f"{c.rule_id}: {c.message}")

    return {
        "score": result.quality_score,
        "grade": result.grade,
        "passed": passed,
        "failed": [
            {
                "rule_id": c.rule_id,
                "message": c.message,
                "text": c.text,
                "details": c.details,
                "fix_hint": c.fix_hint,
            }
            for c in result.checks
            if not c.passed
        ],
    }


def _has_actionable_detail(check: CheckResult) -> bool:
    """Return True if a passing check carries detail the agent should surface.

    Checks for non-empty list-valued keys: missing, locations, matches,
    issues, errors, top_offenders.
    """
    if not check.details:
        return False
    for key in ("missing", "locations", "matches", "issues", "errors", "top_offenders"):
        items = check.details.get(key)
        if items and len(items) > 0:
            return True
    return False
