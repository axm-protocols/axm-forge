"""Text renderers for GitPushTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.push.GitPushTool` into a compact text representation::

    git_push | ✓ | {branch} → {remote} [· upstream set]
    git_push | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow *value* to ``list[str]`` (heterogeneous payload)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    ``{"branch", "remote", "pushed", "set_upstream"}`` →
    ``git_push | ✓ | {branch} → {remote}[ · upstream set]``.
    """
    branch = _as_str(data.get("branch"))
    remote = _as_str(data.get("remote"))
    header = f"git_push | ✓ | {branch} → {remote}"
    if data.get("set_upstream"):
        header += " · upstream set"
    force_mode = data.get("force_mode")
    if force_mode:
        header += f" · {force_mode}"
    return header


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation.

    Lists dirty paths when *data* carries ``dirty_files`` (tree not clean),
    or a child-repo hint when *data* carries ``suggestions`` (not-a-repo).
    """
    header = f"git_push | ✗ | {error}"
    if data is None:
        return header
    dirty = _as_str_list(data.get("dirty_files"))
    if dirty:
        return f"{header}\ndirty: {', '.join(dirty)}"
    suggestions = _as_str_list(data.get("suggestions"))
    if suggestions:
        return f"{header}\nhint: pass one as path: {', '.join(suggestions)}"
    return header
