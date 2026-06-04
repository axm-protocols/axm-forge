"""Text renderers for GitTagTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.tag.GitTagTool` into a compact text representation::

    git_tag | ✓ | {tag} · {bump} [· breaking] · {n} commits · pushed
    resolved {resolved_version} · CI {ci_check} · prev {current_tag}

    git_tag | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    """Narrow *value* to ``int`` (heterogeneous payload)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow *value* to ``list[str]`` (heterogeneous payload)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    Header carries tag, bump type, breaking flag, commit count and push
    status; a second line carries the hatch-vcs resolved version (when
    available), the CI status and the previous tag.
    """
    tag = _as_str(data.get("tag"))
    bump = _as_str(data.get("bump"))
    sections = [tag, bump]
    if data.get("breaking"):
        sections.append("breaking")
    sections.append(f"{_as_int(data.get('commits_included'))} commits")
    sections.append("pushed" if data.get("pushed") else "not pushed")
    header = f"git_tag | ✓ | {' · '.join(sections)}"

    detail: list[str] = []
    resolved = _as_str(data.get("resolved_version"))
    if resolved:
        detail.append(f"resolved {resolved}")
    ci_check = _as_str(data.get("ci_check"))
    if ci_check:
        detail.append(f"CI {ci_check}")
    detail.append(f"prev {_as_str(data.get('current_tag'), 'none')}")
    return f"{header}\n{' · '.join(detail)}"


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation.

    Surfaces ``dirty_files`` (uncommitted changes), ``current_tag``
    (no commits since last tag), ``ci_check`` (CI red), or ``suggestions``
    (not-a-repo) when present in *data*.
    """
    header = f"git_tag | ✗ | {error}"
    if data is None:
        return header
    dirty = _as_str_list(data.get("dirty_files"))
    if dirty:
        return f"{header}\ndirty: {', '.join(dirty)}"
    suggestions = _as_str_list(data.get("suggestions"))
    if suggestions:
        return f"{header}\nhint: pass one as path: {', '.join(suggestions)}"
    current_tag = data.get("current_tag")
    if current_tag is not None:
        return f"{header}\nprev {_as_str(current_tag, 'none')}"
    ci_check = data.get("ci_check")
    if ci_check is not None:
        return f"{header}\nCI {_as_str(ci_check)}"
    return header
