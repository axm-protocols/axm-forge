"""Text renderers for GitBranchTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.branch.GitBranchTool` into a compact, token-efficient
text representation, following the AXM header convention::

    git_branch | ✓ | {branch}
    git_branch | ✗ | {error}
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
    """Render the success-path ``data`` dict (``{"branch": ...}``)."""
    return f"git_branch | ✓ | {_as_str(data.get('branch'))}"


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation.

    Appends a child-repo hint line when *data* carries ``suggestions``
    (the not-a-repo enrichment from :func:`not_a_repo_error`).
    """
    header = f"git_branch | ✗ | {error}"
    suggestions = _as_str_list(data.get("suggestions")) if data else []
    if suggestions:
        return f"{header}\nhint: pass one as path: {', '.join(suggestions)}"
    return header
