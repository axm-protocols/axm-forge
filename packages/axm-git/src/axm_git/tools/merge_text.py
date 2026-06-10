"""Text renderers for GitMergeTool dual-format ToolResult.

git_merge | ✓ | {branch} → {into} (squash)
git_merge | ✗ | {error}
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous payload)."""
    return value if isinstance(value, str) else default


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict."""
    branch = _as_str(data.get("merged"))
    into = _as_str(data.get("into"))
    return f"git_merge | ✓ | {branch} → {into} (squash)"


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation."""
    return f"git_merge | ✗ | {error}"
