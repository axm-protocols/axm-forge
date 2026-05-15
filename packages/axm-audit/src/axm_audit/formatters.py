"""Output formatters for audit results — human-readable and JSON."""

from __future__ import annotations

import logging
from collections.abc import Sized

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
    if not check.passed or check.score is None:
        return False
    return check.score < PERFECT_SCORE


def _format_one_improvement(check: CheckResult) -> list[str]:
    """Format a single improvement entry."""
    score: int | str = check.score if check.score is not None else "?"
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


def format_json(result: AuditResult) -> dict[str, object]:
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


def _drop_nulls(d: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in d.items() if v is not None}


def _render_passed_entry(c: CheckResult) -> str | dict[str, object]:
    metadata = getattr(c, "metadata", None) or None
    if not _has_actionable_detail(c) and not metadata:
        return f"{c.rule_id}: {c.message}"
    if c.text:
        detail: dict[str, object] = {"text": c.text}
    elif c.details is not None:
        detail = {"details": c.details}
    else:
        detail = {}
    entry = _drop_nulls({"rule_id": c.rule_id, "message": c.message, **detail})
    if metadata:
        entry["metadata"] = metadata
    if c.fix_hint:
        entry["fix_hint"] = c.fix_hint
    return entry


def _render_failed_entry(c: CheckResult) -> dict[str, object]:
    if c.text:
        detail: dict[str, object] = {"text": c.text}
    elif c.details is not None:
        detail = {"details": c.details}
    else:
        detail = {}
    metadata = getattr(c, "metadata", None) or None
    return _drop_nulls(
        {
            "rule_id": c.rule_id,
            "message": c.message,
            **detail,
            "metadata": metadata,
            "fix_hint": c.fix_hint,
        }
    )


def format_agent(result: AuditResult) -> dict[str, object]:
    """Agent-optimized output: passed=summary, failed=full detail.

    Minimizes tokens for passing checks while giving full context on
    failures.  For failed checks, ``text`` and ``details`` are both included
    when present (``None`` values are omitted).  Passed checks that
    carry actionable detail (e.g. missing docstrings) are promoted to dicts.
    Rule-specific ``metadata`` (e.g. tautology verdicts, duplicate clusters,
    pyramid mismatches) is propagated verbatim under the ``metadata`` key
    on both passed and failed entries when non-empty.
    """
    return {
        "score": result.quality_score,
        "grade": result.grade,
        "passed": [_render_passed_entry(c) for c in result.checks if c.passed],
        "failed": [_render_failed_entry(c) for c in result.checks if not c.passed],
    }


def _render_passed(passed: list[str | dict[str, object]]) -> list[str]:
    rule_ids: list[str] = [
        str(p.get("rule_id", "?")) if isinstance(p, dict) else p.split(":")[0]
        for p in passed
    ]
    return [f"✓ {' '.join(rule_ids[i : i + 5])}" for i in range(0, len(rule_ids), 5)]


def _render_text_or_details(f: dict[str, object]) -> list[str]:
    text = f.get("text")
    if isinstance(text, str) and text:
        return [f"  {tl}" for tl in text.splitlines()]
    details = f.get("details")
    if isinstance(details, dict):
        return [f"  {dk}: {dv}" for dk, dv in details.items()]
    return []


def _render_verdict_entries(meta: dict[str, object]) -> list[str]:
    out: list[str] = []
    raw_verdicts = meta.get("verdicts", []) or []
    if not isinstance(raw_verdicts, list):
        return out
    for verdict in raw_verdicts:
        if isinstance(verdict, dict):
            tag = verdict.get("verdict") or "UNKNOWN"
            out.append(
                f"  [{tag}] {verdict.get('test', '?')} "
                f"({verdict.get('file', '?')}:{verdict.get('line', '?')})"
            )
    return out


def _render_metadata(meta: object) -> list[str]:
    if not isinstance(meta, dict):
        return []
    return _render_verdict_entries(meta)


def _render_fix(f: dict[str, object]) -> list[str]:
    fix_hint = f.get("fix_hint")
    return [f"  fix: {fix_hint}"] if fix_hint else []


def _render_failed_check(f: dict[str, object]) -> list[str]:
    rule_id = f.get("rule_id", "?")
    message = f.get("message", "")
    lines: list[str] = [f"✗ {rule_id} {message}"]
    lines.extend(_render_text_or_details(f))
    lines.extend(_render_metadata(f.get("metadata")))
    lines.extend(_render_fix(f))
    return lines


def format_agent_text(
    data: dict[str, object],
    category: str | None = None,
) -> str:
    """Render agent-format audit data as compact text for LLM consumption.

    Consumes the dict produced by ``format_agent`` and returns a minimal
    text representation optimised for token count.
    """
    score = data.get("score")
    grade = data.get("grade")
    raw_passed = data.get("passed", [])
    raw_failed = data.get("failed", [])
    passed: list[str | dict[str, object]] = (
        list(raw_passed) if isinstance(raw_passed, list) else []
    )
    failed: list[dict[str, object]] = (
        [f for f in raw_failed if isinstance(f, dict)]
        if isinstance(raw_failed, list)
        else []
    )

    cat_label = f" {category}" if category else ""
    score_part = f" {grade} {score}" if score is not None and grade is not None else ""
    header = f"audit{cat_label} |{score_part} | {len(passed)} pass · {len(failed)} fail"
    lines: list[str] = [header]

    lines.extend(_render_passed(passed))
    for f in failed:
        lines.extend(_render_failed_check(f))

    return "\n".join(lines)


def _legacy_private_entry(f: dict[str, object]) -> dict[str, object]:
    return {
        "file": f.get("test_file") or f.get("file") or "",
        "line": f.get("line", 0),
        "symbol": f.get("private_symbol") or f.get("symbol") or "",
    }


def _dict_items(value: object) -> list[dict[str, object]]:
    """Coerce ``value`` to a list of dict entries, dropping non-dict items."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _meta_dict(check: CheckResult) -> dict[str, object]:
    """Return ``check.metadata`` as a dict (possibly empty)."""
    meta = getattr(check, "metadata", None) or {}
    return meta if isinstance(meta, dict) else {}


def _legacy_private_findings(check: CheckResult) -> list[dict[str, object]]:
    """Return legacy ``details.findings`` for PRIVATE rules."""
    rule = (check.rule_id or "").upper()
    if "PRIVATE" not in rule:
        return []
    details = check.details or {}
    return [_legacy_private_entry(f) for f in _dict_items(details.get("findings"))]


def _extract_private(check: CheckResult) -> list[dict[str, object]]:
    """Normalize private-import findings from metadata or legacy ``details``."""
    violations = _dict_items(_meta_dict(check).get("private_import_violations"))
    if violations:
        return violations
    return _legacy_private_findings(check)


def _finding_to_dict(f: object) -> dict[str, object]:
    """Coerce a finding (Pydantic model or mapping) to a plain dict."""
    dump = getattr(f, "model_dump", None)
    if callable(dump):
        result = dump()
        return result if isinstance(result, dict) else {}
    if isinstance(f, dict):
        return f
    return {}


def _pyramid_entry_from_finding(f: object) -> dict[str, object] | None:
    """Map a single pyramid finding (model or dict) to a normalized entry."""
    fd = _finding_to_dict(f)
    current = fd.get("current_level", "")
    detected = fd.get("level", "")
    if current in ("root", detected):
        return None
    return {
        "test": f"{fd.get('path', '')}::{fd.get('function', '')}",
        "current_dir": current,
        "detected_level": detected,
    }


def _extract_pyramid(check: CheckResult) -> list[dict[str, object]]:
    """Normalize pyramid-mismatch entries from metadata or ``findings`` models."""
    mismatches = _dict_items(_meta_dict(check).get("pyramid_mismatches"))
    if mismatches:
        return mismatches
    rule = (check.rule_id or "").upper()
    if "PYRAMID" not in rule:
        return []
    findings = getattr(check, "findings", None) or []
    return [e for f in findings if (e := _pyramid_entry_from_finding(f)) is not None]


def _cluster_entry(cl: dict[str, object]) -> dict[str, object]:
    """Normalize a single duplicate cluster entry."""
    raw_members = cl.get("members") or cl.get("tests") or []
    return {
        "signal": cl.get("signal", "?"),
        "members": [
            {
                "test": m.get("test") or m.get("name") or "?",
                "file": m.get("file", ""),
                "line": m.get("line", 0),
            }
            for m in _dict_items(raw_members)
        ],
    }


def _extract_clusters(check: CheckResult) -> list[dict[str, object]]:
    """Normalize duplicate-test clusters, tolerating ``members``/``tests`` keys."""
    return [_cluster_entry(cl) for cl in _dict_items(_meta_dict(check).get("clusters"))]


def _extract_verdicts(check: CheckResult) -> list[dict[str, object]]:
    """Return per-test quality verdicts attached to ``check.metadata``."""
    return _dict_items(_meta_dict(check).get("verdicts"))


def _extract_no_package_symbol(check: CheckResult) -> list[dict[str, object]]:
    """Pull NO_PACKAGE_SYMBOL findings from the rule's ``details``."""
    if (check.rule_id or "") != "TEST_QUALITY_NO_PACKAGE_SYMBOL":
        return []
    details = check.details or {}
    return _dict_items(details.get("findings"))


def _extract_test_quality(
    result: AuditResult,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Pull (private, pyramid, clusters, verdicts, no_pkg) entries from checks."""
    private: list[dict[str, object]] = []
    pyramid: list[dict[str, object]] = []
    clusters: list[dict[str, object]] = []
    verdicts: list[dict[str, object]] = []
    no_pkg: list[dict[str, object]] = []
    for c in result.checks:
        private.extend(_extract_private(c))
        pyramid.extend(_extract_pyramid(c))
        clusters.extend(_extract_clusters(c))
        verdicts.extend(_extract_verdicts(c))
        no_pkg.extend(_extract_no_package_symbol(c))
    return private, pyramid, clusters, verdicts, no_pkg


def _format_pyramid_only(pyramid: list[dict[str, object]]) -> str:
    mismatches = [m for m in pyramid if m.get("current_dir") != m.get("detected_level")]
    lines = ["Pyramid mismatches:"]
    for m in mismatches:
        lines.append(
            f"  {m.get('test', '?')}  "
            f"{m.get('current_dir', '')} -> {m.get('detected_level', '')}"
        )
    return "\n".join(lines)


def _format_private_section(private: list[dict[str, object]]) -> list[str]:
    lines = ["Private imports:"]
    if not private:
        lines.append("  (none)")
    for p in private:
        lines.append(
            f"  {p.get('file', '?')}:{p.get('line', '?')}  {p.get('symbol', '?')}"
        )
    return lines


def _format_pyramid_section(pyramid: list[dict[str, object]]) -> list[str]:
    lines = ["Pyramid:"]
    if not pyramid:
        lines.append("  (none)")
    for m in pyramid:
        cd = m.get("current_dir", "")
        dl = m.get("detected_level", "")
        flag = "" if cd == dl else "  [MISMATCH]"
        lines.append(f"  {m.get('test', '?')}  {cd} -> {dl}{flag}")
    return lines


def _format_duplicates_section(clusters: list[dict[str, object]]) -> list[str]:
    lines = ["Duplicates:"]
    if not clusters:
        lines.append("  (none)")
    for cl in clusters:
        lines.append(f"  [{cl.get('signal', '?')}]")
        members = cl.get("members", [])
        if not isinstance(members, list):
            continue
        for mem in members:
            if not isinstance(mem, dict):
                continue
            lines.append(
                f"    {mem.get('file', '?')}:{mem.get('line', '?')}  "
                f"{mem.get('test', '?')}"
            )
    return lines


def _format_tautologies_section(verdicts: list[dict[str, object]]) -> list[str]:
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
    private, pyramid, clusters, verdicts, no_pkg = _extract_test_quality(result)

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
    if no_pkg:
        lines.append("")
        lines.append("TEST_QUALITY_NO_PACKAGE_SYMBOL:")
        for entry in no_pkg:
            lines.append(
                f"  [{entry.get('verdict', '?')}] {entry.get('test_file', '?')}"
            )

    return "\n".join(lines)


def format_test_quality_json(result: AuditResult) -> dict[str, object]:
    """JSON superset: clusters + verdicts + pyramid + private violations."""
    private, pyramid, clusters, verdicts, no_pkg = _extract_test_quality(result)
    rule_ids = sorted(
        {
            c.rule_id
            for c in result.checks
            if (c.rule_id or "").startswith("TEST_QUALITY_")
        }
    )
    payload: dict[str, object] = {
        "score": result.quality_score,
        "grade": result.grade,
        "rules": rule_ids,
        "clusters": clusters,
        "verdicts": verdicts,
        "pyramid_mismatches": pyramid,
        "private_import_violations": private,
        "no_package_symbol": [
            {**entry, "rule_id": "TEST_QUALITY_NO_PACKAGE_SYMBOL"} for entry in no_pkg
        ],
    }
    return payload


def _has_actionable_detail(check: CheckResult) -> bool:
    """Return True if a passing check carries detail the agent should surface.

    Checks for non-empty list-valued keys: missing, locations, matches,
    issues, errors, top_offenders.
    """
    if not check.details:
        return False
    for key in ("missing", "locations", "matches", "issues", "errors", "top_offenders"):
        items = check.details.get(key)
        if items and isinstance(items, Sized) and len(items) > 0:
            return True
    return False
