"""Text renderers for ``git_release_diff`` (dual-format ToolResult)."""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    """Narrow *value* to ``int`` (heterogeneous payload)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    Header carries the current tag, the suggested bump + next version, the
    breaking flag and the commit count; a second line carries the diffstat,
    files changed and the public-API flag.
    """
    current = _as_str(data.get("current_tag"), "none")
    bump = _as_str(data.get("suggested_bump"))
    nxt = _as_str(data.get("suggested_next"))
    commits = data.get("commits_since")
    count = len(commits) if isinstance(commits, list) else 0
    sections = [current, f"{bump} -> {nxt}"]
    if data.get("breaking"):
        sections.append("breaking")
    sections.append(f"{count} commits")
    header = f"git_release_diff | ✓ | {' · '.join(sections)}"

    detail = [
        _as_str(data.get("diffstat"), "+0 / -0"),
        f"{_as_int(data.get('files_changed'))} files",
    ]
    if data.get("public_api_touched"):
        detail.append("public API touched")
    base = f"{header}\n{' · '.join(detail)}"

    block = _render_commits(data)
    return f"{base}\n{block}" if block else base


def _render_commits(data: dict[str, object]) -> str:
    """Render the per-type summary line plus one line per commit.

    Returns an empty string when there are no commits, so the caller appends
    nothing (no summary line, no trailing blank line).
    """
    commits = data.get("commits_since")
    if not isinstance(commits, list) or not commits:
        return ""

    counts = data.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    summary = [
        f"{kind} {n}"
        for kind in ("feat", "fix", "breaking", "other")
        if (n := _as_int(counts.get(kind))) > 0
    ]

    lines = [" · ".join(summary)] if summary else []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
        hash_ = _as_str(commit.get("hash"))
        type_ = _as_str(commit.get("type"))
        marker = "!" if commit.get("breaking") else ""
        subject = _as_str(commit.get("subject"))
        lines.append(f"{hash_} {type_}{marker}: {subject}")
    return "\n".join(lines)


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation."""
    header = f"git_release_diff | ✗ | {error}"
    if data is None:
        return header
    current = data.get("current_tag")
    if current is not None:
        return f"{header}\nprev {_as_str(current, 'none')}"
    return header
