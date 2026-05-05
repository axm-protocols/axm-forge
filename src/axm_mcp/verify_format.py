"""Compact text rendering for ``verify_project`` results.

The raw verify dict can reach 20k-80k tokens (esp. when
``TEST_QUALITY_DUPLICATE_TESTS`` returns 100+ clusters). The agent is
the only consumer, so we drop the raw data and emit a compact text
report instead.

Rendering policy:

- ``finding.text``: trust the rule — already compact, just indent each
  line by 2 spaces for visual coherence.
- ``finding.details``: descend (str → indent; list → top-N items;
  dict → look up known thematic keys, else JSON-truncate fallback).
- ``finding.metadata`` (with ``clusters``): keep legacy cluster summary.
- ``fix_hint`` is shown verbatim, never truncated.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["format_verify_text"]

_INDENT = "  "
_LIST_PREVIEW = 30
_DICT_FALLBACK_MAX = 500
_HEADER_ERROR_MAX = 60

# Ordered preference for thematic list keys inside ``details`` dicts.
_KNOWN_LIST_KEYS: tuple[str, ...] = (
    "findings",
    "violations",
    "issues",
    "errors",
    "matches",
    "top_offenders",
    "clones",
    "locations",
    "missing",
    "mismatches",
    "cycles",
    "god_classes",
    "over_threshold",
    "top_vulns",
    "unformatted_files",
    "top_issues",
    "symbols",
    "verdicts",
)


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


# ── Header ────────────────────────────────────────────────────────────


def _format_header(audit: Any, governance: Any) -> str:
    audit_h = _section_header("audit", audit)
    gov_h = _section_header("governance", governance)
    return f"verify | {audit_h} · {gov_h}"


def _section_header(label: str, section: Any) -> str:
    if not isinstance(section, dict):
        return f"{label}: skipped"
    if "error" in section and len(section) == 1:
        err = str(section["error"]).replace("\n", " ").strip()
        if len(err) > _HEADER_ERROR_MAX:
            err = err[: _HEADER_ERROR_MAX - 1].rstrip() + "…"
        return f"{label}: error ({err})"
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


# ── Finding / governance dispatch ─────────────────────────────────────


def _format_finding(failure: dict[str, Any]) -> str:
    rule_id = failure.get("rule_id", "?")
    message = failure.get("message", "")
    lines = [f"✗ {rule_id} · {message}".rstrip(" ·")]

    detail_lines = _render_finding_detail(failure)
    lines.extend(detail_lines)

    fix_hint = failure.get("fix_hint")
    if fix_hint:
        lines.append(f"{_INDENT}fix: {str(fix_hint).rstrip()}")

    return "\n".join(lines)


def _format_governance(check: dict[str, Any]) -> str:
    name = check.get("name", "?")
    message = check.get("message", "")
    lines = [f"✗ {name} · {message}".rstrip(" ·")]

    detail_lines = _render_finding_detail(check)
    lines.extend(detail_lines)

    fix = check.get("fix")
    if fix:
        lines.append(f"{_INDENT}fix: {str(fix).rstrip()}")
    return "\n".join(lines)


# ── Detail rendering ──────────────────────────────────────────────────


def _render_finding_detail(failure: dict[str, Any]) -> list[str]:
    """Return indented detail lines for a finding-like dict.

    Resolution order: ``text`` → ``details`` → ``metadata.clusters``.
    Returns an empty list when nothing meaningful is available.
    """
    text = failure.get("text")
    if isinstance(text, str) and text.strip():
        return _indent_block(text)

    if "details" in failure:
        details = failure.get("details")
        if details or details == 0:
            rendered = _render_details(details)
            if rendered:
                return rendered

    metadata = failure.get("metadata")
    if isinstance(metadata, dict):
        summary = _summarize_metadata(metadata)
        if summary:
            return [f"{_INDENT}{summary}"]

    return []


def _indent_block(text: str) -> list[str]:
    """Indent every line of *text* uniformly with ``_INDENT``."""
    return [f"{_INDENT}{line}" for line in text.rstrip("\n").splitlines()]


def _render_details(details: Any) -> list[str]:
    """Render a ``details`` payload (str / list / dict) as indented lines."""
    if isinstance(details, str):
        if not details.strip():
            return []
        return _indent_block(details)
    if isinstance(details, list):
        return _render_list_details(details)
    if isinstance(details, dict):
        return _render_dict_details(details)
    return []


def _render_list_details(items: list[Any]) -> list[str]:
    if not items:
        return []
    lines = [f"{_INDENT}- {_compact_item(item)}" for item in items[:_LIST_PREVIEW]]
    extra = len(items) - _LIST_PREVIEW
    if extra > 0:
        lines.append(f"{_INDENT}(+{extra} more)")
    return lines


def _render_dict_details(details: dict[str, Any]) -> list[str]:
    """Find a thematic list under a known key, else JSON fallback."""
    for key in _KNOWN_LIST_KEYS:
        value = details.get(key)
        if isinstance(value, list) and value:
            return _render_list_details(value)
    # Fallback: dump the whole dict, truncated.
    try:
        dumped = json.dumps(details, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        dumped = str(details)
    if len(dumped) > _DICT_FALLBACK_MAX:
        dumped = dumped[: _DICT_FALLBACK_MAX - 1].rstrip() + "…"
    return [f"{_INDENT}{dumped}"]


def _compact_item(item: Any) -> str:
    """Render one list item compactly.

    - ``{"file": "...", "line": N, "msg"/"message": "..."}`` → ``file:line msg``.
    - other dicts → JSON
    - scalars → ``str(item)``
    """
    if isinstance(item, dict):
        file_ = item.get("file") or item.get("path")
        line = item.get("line") or item.get("lineno")
        msg = item.get("msg") or item.get("message") or item.get("reason")
        if file_ and msg is not None:
            location = f"{file_}:{line}" if line is not None else str(file_)
            return f"{location} {msg}"
        try:
            return json.dumps(item, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(item)
    return str(item)


# ── Metadata / clusters ───────────────────────────────────────────────


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
