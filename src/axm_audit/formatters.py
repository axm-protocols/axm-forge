"""Output formatters for audit results — human-readable and JSON."""

from __future__ import annotations

from typing import Any

from axm_audit.models.results import AuditResult, CheckResult

_GRADE_EMOJI = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}

# ── Detail formatters (per rule type) ────────────────────────────────

_INDENT = "     "


def _complexity_details(details: dict[str, Any]) -> list[str]:
    """Format complexity top offenders."""
    return [
        f"{_INDENT}• {o['file']} → {o['function']} (cc={o['cc']})"
        for o in details.get("top_offenders", [])
    ]


def _security_details(details: dict[str, Any]) -> list[str]:
    """Format Bandit security issues."""
    return [
        f"{_INDENT}• [{i['severity']}] {i['code']}: "
        f"{i['message']} ({i['file']}:{i['line']})"
        for i in details.get("top_issues", [])
    ]


def _vuln_details(details: dict[str, Any]) -> list[str]:
    """Format vulnerable packages."""
    return [
        f"{_INDENT}• {v['name']}=={v['version']}" for v in details.get("top_vulns", [])
    ]


def _hygiene_details(details: dict[str, Any]) -> list[str]:
    """Format deptry hygiene issues."""
    return [
        f"{_INDENT}• [{i['code']}] {i['module']}: {i['message']}"
        for i in details.get("top_issues", [])
    ]


def _coverage_details(details: dict[str, Any]) -> list[str]:
    """Format coverage details."""
    cov = details.get("coverage")
    if cov is not None and cov < 100:
        return [f"{_INDENT}• Coverage: {cov:.1f}% → target: 100%"]
    return []


# Dispatch table: rule_id → detail formatter
_DETAIL_FORMATTERS: dict[str, Any] = {
    "QUALITY_COMPLEXITY": _complexity_details,
    "QUALITY_SECURITY": _security_details,
    "DEPS_AUDIT": _vuln_details,
    "DEPS_HYGIENE": _hygiene_details,
    "QUALITY_COVERAGE": _coverage_details,
}


def _format_check_details(check: CheckResult) -> list[str]:
    """Extract contextual detail lines from a check result.

    Returns bullet-point strings for display.
    Returns empty list for checks at score=100 or without details.
    """
    if not check.details:
        return []

    score = check.details.get("score")
    if score is not None and score >= 100:
        return []

    formatter = _DETAIL_FORMATTERS.get(check.rule_id)
    if formatter:
        result: list[str] = formatter(check.details)
        return result
    return []


# ── Report section formatters ────────────────────────────────────────


def _format_categories(result: AuditResult) -> list[str]:
    """Format category breakdown section."""
    groups: dict[str, list[CheckResult]] = {}
    for check in result.checks:
        cat = _category_for(check.rule_id)
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
    return score is not None and score < 100


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
        f"   Path: {result.checks[0].rule_id if result.checks else '?'}",
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


def _category_for(rule_id: str) -> str:
    """Map a rule_id to its display category."""
    prefixes = {
        "QUALITY_": "quality",
        "DEPS_": "dependencies",
        "PRACTICE_": "practices",
        "ARCH_": "architecture",
        "TOOL_": "tooling",
        "STRUCTURE_": "structure",
    }
    for prefix, category in prefixes.items():
        if rule_id.startswith(prefix):
            return category
    return "other"
