"""Text renderers for GitPRTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.pr.GitPRTool` into a compact text representation::

    git_pr | ✓ | #{pr_number} [· auto-merge]
    {pr_url}
    git_pr | ✗ | {error}
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

    ``{"pr_url", "pr_number", "auto_merge"}`` → ``#{number}[ · auto-merge]``
    header plus the PR url on the next line.
    """
    number = _as_str(data.get("pr_number"))
    header = f"git_pr | ✓ | #{number}"
    if data.get("auto_merge"):
        header += " · auto-merge"
    url = _as_str(data.get("pr_url"))
    return f"{header}\n{url}" if url else header


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation.

    Appends a child-repo hint when *data* carries ``suggestions``
    (the not-a-repo enrichment).
    """
    header = f"git_pr | ✗ | {error}"
    suggestions = _as_str_list(data.get("suggestions")) if data else []
    if suggestions:
        return f"{header}\nhint: pass one as path: {', '.join(suggestions)}"
    return header
