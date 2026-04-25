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
        return [f"     {line}" for line in check.text.splitlines()]
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
    failures.  For failed checks, ``text`` and ``details`` are both included
    when present (``None`` values are omitted).  Passed checks that
    carry actionable detail (e.g. missing
    docstrings) are promoted to dicts.
    """
    passed: list[str | dict[str, Any]] = []
    for c in result.checks:
        if not c.passed:
            continue
        if _has_actionable_detail(c):
            entry: dict[str, Any] = {
                k: v
                for k, v in {
                    "rule_id": c.rule_id,
                    "message": c.message,
                    **({"text": c.text} if c.text else {"details": c.details}),
                }.items()
                if v is not None
            }
            if c.fix_hint:
                entry["fix_hint"] = c.fix_hint
            passed.append(entry)
        else:
            passed.append(f"{c.rule_id}: {c.message}")

    return {
        "score": result.quality_score,
        "grade": result.grade,
        "passed": passed,
        "failed": [
            {
                k: v
                for k, v in {
                    "rule_id": c.rule_id,
                    "message": c.message,
                    **(
                        ({"text": c.text} if c.text else {"details": c.details})
                        if c.text or c.details is not None
                        else {}
                    ),
                    "fix_hint": c.fix_hint,
                }.items()
                if v is not None
            }
            for c in result.checks
            if not c.passed
        ],
    }


def format_agent_text(  # noqa: PLR0912
    data: dict[str, Any],
    category: str | None = None,
) -> str:
    """Render agent-format audit data as compact text for LLM consumption.

    Consumes the dict produced by ``format_agent`` and returns a minimal
    text representation optimised for token count.
    """
    score = data.get("score")
    grade = data.get("grade")
    passed = data.get("passed", [])
    failed = data.get("failed", [])

    # Header
    cat_label = f" {category}" if category else ""
    score_part = f" {grade} {score}" if score is not None and grade is not None else ""
    header = f"audit{cat_label} |{score_part} | {len(passed)} pass · {len(failed)} fail"
    lines: list[str] = [header]

    # Passed section — group rule_ids on ✓ lines (≤5 per line)
    if passed:
        rule_ids: list[str] = []
        for p in passed:
            if isinstance(p, dict):
                rule_ids.append(p.get("rule_id", "?"))
            else:
                rule_ids.append(p.split(":")[0])
        for i in range(0, len(rule_ids), 5):
            chunk = rule_ids[i : i + 5]
            lines.append(f"✓ {' '.join(chunk)}")

    # Failed section
    for f in failed:
        rule_id = f.get("rule_id", "?")
        message = f.get("message", "")
        lines.append(f"✗ {rule_id} {message}")
        text = f.get("text")
        if text:
            for tl in text.splitlines():
                lines.append(f"  {tl}")
        elif "details" in f and isinstance(f["details"], dict):
            details = f["details"]
            for dk, dv in details.items():
                lines.append(f"  {dk}: {dv}")
        meta = f.get("metadata")
        if isinstance(meta, dict):
            for verdict in meta.get("verdicts", []) or []:
                if isinstance(verdict, dict):
                    tag = verdict.get("verdict") or "UNKNOWN"
                    lines.append(
                        f"  [{tag}] {verdict.get('test', '?')} "
                        f"({verdict.get('file', '?')}:{verdict.get('line', '?')})"
                    )
            for cluster in meta.get("clusters", []) or []:
                if isinstance(cluster, dict):
                    members = cluster.get("members") or cluster.get("tests") or []
                    lines.append(
                        f"  [{cluster.get('signal', '?')}] {len(members)} test(s)"
                    )
        fix_hint = f.get("fix_hint")
        if fix_hint:
            lines.append(f"  fix: {fix_hint}")

    return "\n".join(lines)


def _extract_test_quality(
    result: AuditResult,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Pull (private, pyramid, clusters, verdicts) entries from any check shape."""
    private: list[dict[str, Any]] = []
    pyramid: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []

    for c in result.checks:
        meta = getattr(c, "metadata", None) or {}
        details = c.details or {}
        rule = (c.rule_id or "").upper()

        if meta.get("private_import_violations"):
            private.extend(meta["private_import_violations"])
        elif "PRIVATE" in rule and details.get("findings"):
            for f in details["findings"]:
                private.append(
                    {
                        "file": f.get("test_file") or f.get("file") or "",
                        "line": f.get("line", 0),
                        "symbol": (f.get("private_symbol") or f.get("symbol") or ""),
                    }
                )

        if meta.get("pyramid_mismatches"):
            pyramid.extend(meta["pyramid_mismatches"])
        elif "PYRAMID" in rule:
            findings = getattr(c, "findings", None) or []
            for f in findings:
                fd = f.model_dump() if hasattr(f, "model_dump") else dict(f)
                pyramid.append(
                    {
                        "test": f"{fd.get('path', '')}::{fd.get('function', '')}",
                        "current_dir": fd.get("current_level", ""),
                        "detected_level": fd.get("level", ""),
                    }
                )

        if meta.get("clusters"):
            for cl in meta["clusters"]:
                members_raw = cl.get("members") or cl.get("tests") or []
                clusters.append(
                    {
                        "signal": cl.get("signal", "?"),
                        "members": [
                            {
                                "test": m.get("test") or m.get("name") or "?",
                                "file": m.get("file", ""),
                                "line": m.get("line", 0),
                            }
                            for m in members_raw
                        ],
                    }
                )

        if meta.get("verdicts"):
            verdicts.extend(meta["verdicts"])

    return private, pyramid, clusters, verdicts


def _format_pyramid_only(pyramid: list[dict[str, Any]]) -> str:
    mismatches = [m for m in pyramid if m.get("current_dir") != m.get("detected_level")]
    lines = ["Pyramid mismatches:"]
    for m in mismatches:
        lines.append(
            f"  {m.get('test', '?')}  "
            f"{m.get('current_dir', '')} -> {m.get('detected_level', '')}"
        )
    return "\n".join(lines)


def _format_private_section(private: list[dict[str, Any]]) -> list[str]:
    lines = ["Private imports:"]
    if not private:
        lines.append("  (none)")
    for p in private:
        lines.append(
            f"  {p.get('file', '?')}:{p.get('line', '?')}  {p.get('symbol', '?')}"
        )
    return lines


def _format_pyramid_section(pyramid: list[dict[str, Any]]) -> list[str]:
    lines = ["Pyramid:"]
    if not pyramid:
        lines.append("  (none)")
    for m in pyramid:
        cd = m.get("current_dir", "")
        dl = m.get("detected_level", "")
        flag = "" if cd == dl else "  [MISMATCH]"
        lines.append(f"  {m.get('test', '?')}  {cd} -> {dl}{flag}")
    return lines


def _format_duplicates_section(clusters: list[dict[str, Any]]) -> list[str]:
    lines = ["Duplicates:"]
    if not clusters:
        lines.append("  (none)")
    for cl in clusters:
        lines.append(f"  [{cl.get('signal', '?')}]")
        for mem in cl.get("members", []):
            lines.append(
                f"    {mem.get('file', '?')}:{mem.get('line', '?')}  "
                f"{mem.get('test', '?')}"
            )
    return lines


def _format_tautologies_section(verdicts: list[dict[str, Any]]) -> list[str]:
    lines = ["Tautologies:"]
    if not verdicts:
        lines.append("  (none)")
    for v in verdicts:
        tag = v.get("verdict") or "UNKNOWN"
        lines.append(
            f"  [{tag}] {v.get('test', '?')}  {v.get('file', '?')}:{v.get('line', '?')}"
        )
    return lines


def format_test_quality_text(
    result: AuditResult,
    mismatches_only: bool = False,
) -> str:
    """Render test-quality findings grouped by rule.

    Order: private imports → pyramid → duplicates → tautologies.
    With ``mismatches_only=True`` only the pyramid section is emitted,
    filtered to entries whose folder differs from the classified level.
    """
    private, pyramid, clusters, verdicts = _extract_test_quality(result)

    if mismatches_only:
        return _format_pyramid_only(pyramid)

    lines: list[str] = []
    lines.extend(_format_private_section(private))
    lines.append("")
    lines.extend(_format_pyramid_section(pyramid))
    lines.append("")
    lines.extend(_format_duplicates_section(clusters))
    lines.append("")
    lines.extend(_format_tautologies_section(verdicts))

    return "\n".join(lines)


def format_test_quality_json(result: AuditResult) -> dict[str, Any]:
    """JSON superset: clusters + verdicts + pyramid + private violations."""
    private, pyramid, clusters, verdicts = _extract_test_quality(result)
    return {
        "score": result.quality_score,
        "grade": result.grade,
        "clusters": clusters,
        "verdicts": verdicts,
        "pyramid_mismatches": pyramid,
        "private_import_violations": private,
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
