"""Text renderers for GitPullTool dual-format ToolResult.

git_pull | ✓ | {remote}/{branch}
git_pull | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous payload)."""
    return value if isinstance(value, str) else default


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict."""
    remote = _as_str(data.get("remote"))
    branch = _as_str(data.get("branch"))
    return f"git_pull | ✓ | {remote}/{branch}"


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation."""
    return f"git_pull | ✗ | {error}"
