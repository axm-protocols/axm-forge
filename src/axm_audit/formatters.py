"""Output formatters for audit results — human-readable and JSON."""

from __future__ import annotations

from typing import Any

from axm_audit.models.results import AuditResult


def format_report(result: AuditResult) -> str:
    """Format audit result as human-readable category-grouped report."""
    lines: list[str] = []
    lines.append("📋 axm-audit — Quality Audit")
    lines.append(f"   Path: {result.checks[0].rule_id if result.checks else '?'}")
    lines.append("")

    # Group checks by category prefix
    categories: dict[str, list[tuple[str, bool, str]]] = {}
    for check in result.checks:
        cat = _category_for(check.rule_id)
        categories.setdefault(cat, []).append(
            (check.rule_id, check.passed, check.message)
        )

    for cat_name, checks in categories.items():
        lines.append(f"  {cat_name}")
        for rule_id, passed, message in checks:
            status = "✅" if passed else "❌"
            lines.append(f"    {status} {rule_id:<30s}  {message}")
        lines.append("")

    # Score and grade
    grade_emoji = {"A": "🏆", "B": "✅", "C": "⚠️", "D": "🔧", "F": "❌"}
    if result.quality_score is not None:
        emoji = grade_emoji.get(result.grade or "", "")
        lines.append(
            f"  Score: {result.quality_score}/100 — Grade {result.grade} {emoji}"
        )
    lines.append("")

    # Failures
    failed_checks = [c for c in result.checks if not c.passed]
    if failed_checks:
        lines.append(f"  📝 Failures ({len(failed_checks)}):")
        lines.append("")
        for check in failed_checks:
            lines.append(f"  ❌ {check.rule_id}")
            lines.append(f"     Problem: {check.message}")
            if check.fix_hint:
                lines.append(f"     Fix:     {check.fix_hint}")
            lines.append("")

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
    if rule_id.startswith("QUALITY_"):
        return "quality"
    if rule_id.startswith("DEPS_"):
        return "dependencies"
    if (
        rule_id.startswith("STRUCTURE_")
        or rule_id.startswith("FILE_")
        or rule_id.startswith("DIR_")
    ):
        return "structure"
    if rule_id.startswith("PRACTICE_"):
        return "practices"
    if rule_id.startswith("ARCH_"):
        return "architecture"
    if rule_id.startswith("TOOL_"):
        return "tooling"
    return "other"
