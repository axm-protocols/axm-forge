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
    return f"{header}\n{' · '.join(detail)}"


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation."""
    header = f"git_release_diff | ✗ | {error}"
    if data is None:
        return header
    current = data.get("current_tag")
    if current is not None:
        return f"{header}\nprev {_as_str(current, 'none')}"
    return header
