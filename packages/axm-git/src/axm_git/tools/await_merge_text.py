"""Text renderers for GitAwaitMergeTool dual-format ToolResult.

git_await_merge | ✓ | PR {pr_ref} merged
git_await_merge | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous payload)."""
    return value if isinstance(value, str) else default


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict."""
    return f"git_await_merge | ✓ | PR {_as_str(data.get('pr_ref'))} merged"


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation."""
    return f"git_await_merge | ✗ | {error}"
