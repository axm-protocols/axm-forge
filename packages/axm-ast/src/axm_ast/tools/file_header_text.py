"""Text renderer for AstFileHeaderTool dual-format ToolResult.

ast_file_header | ✓ | {n} file(s)
<file>
<header>
...
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]


def render_text(headers: list[dict[str, str]]) -> str:
    """Render the success-path headers list as compact text."""
    lines = [f"ast_file_header | ✓ | {len(headers)} file(s)"]
    for entry in headers:
        lines.append(f"\n# {entry.get('file', '')}")
        lines.append(entry.get("header", "").rstrip())
    return "\n".join(lines)


def render_failure_text(*, error: str) -> str:
    """Render the failure-path text representation."""
    return f"ast_file_header | ✗ | {error}"
