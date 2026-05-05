"""Compact text rendering for ``verify_project`` results.

The raw verify dict can reach 20k-80k tokens (esp. when
``TEST_QUALITY_DUPLICATE_TESTS`` returns 100+ clusters). The agent is
the only consumer, so we drop the raw data and emit a compact text
report instead.
"""

from __future__ import annotations

from typing import Any

__all__ = ["format_verify_text"]

_DETAIL_MAX = 120
_FIX_MAX = 150
_LIST_PREVIEW = 3


def format_verify_text(result: dict[str, Any]) -> str:
    """Render a verify_project result as a compact text report.

    Args:
        result: Output of ``verify_project`` — dict with ``audit`` and
            ``governance`` keys (each optional / nullable).

    Returns:
        Multi-line string. Always starts with a 1-line header.
    """
    audit = result.get("audit") if isinstance(result, dict) else None
    governance = result.get("governance") if isinstance(result, dict) else None

    parts: list[str] = [_format_header(audit, governance)]

    if isinstance(audit, dict):
        for failure in audit.get("failed", []) or []:
            parts.append("")
            parts.append(_format_finding(failure))

    if isinstance(governance, dict):
        for check in governance.get("failed", []) or []:
            parts.append("")
            parts.append(_format_governance(check))

    return "\n".join(parts)


def _format_header(audit: Any, governance: Any) -> str:
    audit_h = _section_header("audit", audit)
    gov_h = _section_header("governance", governance)
    return f"verify | {audit_h} · {gov_h}"


def _section_header(label: str, section: Any) -> str:
    if not isinstance(section, dict):
        return f"{label}: skipped"
    if "error" in section and len(section) == 1:
        return f"{label}: error ({_truncate(str(section['error']), 60)})"
    grade = section.get("grade", "?")
    score = section.get("score", "?")
    passed_count, total = _counts(section)
    return f"{label} {grade} {score} ({passed_count}/{total})"


def _counts(section: dict[str, Any]) -> tuple[int, int]:
    passed = section.get("passed")
    failed = section.get("failed") or []
    if isinstance(passed, list):
        passed_n = len(passed)
    elif isinstance(passed, int):
        passed_n = passed
    else:
        passed_n = section.get("passed_count", 0) or 0
    failed_n = len(failed) if isinstance(failed, list) else 0
    return passed_n, passed_n + failed_n


def _format_finding(failure: dict[str, Any]) -> str:
    rule_id = failure.get("rule_id", "?")
    message = failure.get("message", "")
    lines = [f"✗ {rule_id} · {message}".rstrip(" ·")]

    detail = _detail_line(failure)
    if detail:
        lines.append(f"  {_truncate(detail, _DETAIL_MAX)}")

    fix_hint = failure.get("fix_hint")
    if fix_hint:
        lines.append(f"  fix: {_truncate(str(fix_hint), _FIX_MAX)}")

    return "\n".join(lines)


def _format_governance(check: dict[str, Any]) -> str:
    name = check.get("name", "?")
    message = check.get("message", "")
    lines = [f"✗ {name} · {message}".rstrip(" ·")]
    details = check.get("details")
    detail_str = _stringify_details(details)
    if detail_str:
        lines.append(f"  {_truncate(detail_str, _DETAIL_MAX)}")
    fix = check.get("fix")
    if fix:
        lines.append(f"  fix: {_truncate(str(fix), _FIX_MAX)}")
    return "\n".join(lines)


def _detail_line(failure: dict[str, Any]) -> str:
    text = failure.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip().replace("\n", " ")

    details = failure.get("details")
    detail_str = _stringify_details(details)
    if detail_str:
        return detail_str

    metadata = failure.get("metadata")
    if isinstance(metadata, dict):
        return _summarize_metadata(metadata)

    return ""


def _stringify_details(details: Any) -> str:
    if isinstance(details, str):
        return details.strip().replace("\n", " ")
    if isinstance(details, list):
        if not details:
            return ""
        previews = [str(d) for d in details[:_LIST_PREVIEW]]
        suffix = (
            f" (+{len(details) - _LIST_PREVIEW} more)"
            if len(details) > _LIST_PREVIEW
            else ""
        )
        return ", ".join(previews) + suffix
    if isinstance(details, dict):
        # E.g. {"findings": [...]} or {"missing_dirs": [...]}
        return _stringify_dict_details(details)
    return ""


def _stringify_dict_details(details: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in list(details.items())[:3]:
        if isinstance(value, list):
            parts.append(f"{key}={len(value)}")
        elif isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _summarize_metadata(metadata: dict[str, Any]) -> str:
    clusters = metadata.get("clusters")
    parts: list[str] = []

    if isinstance(clusters, list) and clusters:
        signals: dict[str, int] = {}
        for c in clusters:
            if isinstance(c, dict):
                sig = c.get("signal", "?")
                signals[sig] = signals.get(sig, 0) + 1
        top = sorted(signals.items(), key=lambda kv: -kv[1])[:3]
        if top:
            parts.append("signals: " + ", ".join(f"{s}={n}" for s, n in top))
        first = clusters[0]
        if isinstance(first, dict):
            members = first.get("members") or []
            sim = first.get("similarity", "?")
            sig = first.get("signal", "?")
            parts.append(f"top cluster: [{sig}] {len(members)} tests sim={sim}")

    bucket_counts = metadata.get("bucket_counts")
    if isinstance(bucket_counts, dict) and bucket_counts:
        bc = ", ".join(f"{k}={v}" for k, v in bucket_counts.items())
        parts.append(f"buckets: {bc}")

    return " · ".join(parts)


def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
