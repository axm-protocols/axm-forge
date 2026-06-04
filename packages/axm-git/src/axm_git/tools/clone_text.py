"""Text renderers for GitCloneTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.clone.GitCloneTool` into a compact text representation::

    git_clone | ✓ | {url} → {dest}
    {path}
    git_clone | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    ``{"url", "dest", "path", "cloned"}`` → header line ``{url} → {dest}``
    plus the absolute clone path on the next line.
    """
    url = _as_str(data.get("url"))
    dest = _as_str(data.get("dest"))
    path = _as_str(data.get("path"))
    header = f"git_clone | ✓ | {url} → {dest}"
    return f"{header}\n{path}" if path else header


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation (clone error)."""
    return f"git_clone | ✗ | {error}"
