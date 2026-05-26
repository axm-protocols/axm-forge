"""ReadFileTool — read file content with optional line-range support.

Registered as ``read_file`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

from axm_edit.core.engine import _resolve_safe
from axm_edit.utils import is_binary

__all__ = ["ReadFileTool"]

logger = logging.getLogger(__name__)


def _validate_line_range(
    start_line: int | None,
    end_line: int | None,
) -> str | None:
    """Validate start/end line arguments.

    Returns an error message string, or ``None`` if valid.
    """
    if start_line is not None and start_line < 1:
        return "start_line must be >= 1"
    if end_line is not None and end_line < 1:
        return "end_line must be >= 1"
    if start_line is not None and end_line is not None and start_line > end_line:
        return f"Invalid range: start_line ({start_line}) > end_line ({end_line})"
    return None


def _resolve_file(
    root_str: str,
    file_rel: str,
) -> Path | ToolResult:
    """Resolve and validate a file path within the project root.

    Returns the resolved ``Path`` on success, or a ``ToolResult``
    error on failure.
    """
    root = Path(root_str).resolve()
    if not root.is_dir():
        return ToolResult(success=False, error=f"Root is not a directory: {root_str}")

    resolved = _resolve_safe(root, file_rel)
    if resolved is None:
        return ToolResult(
            success=False,
            error=f"Path escapes project root: {file_rel}",
        )

    if not resolved.is_file():
        return ToolResult(success=False, error=f"File not found: {file_rel}")

    if is_binary(resolved):
        return ToolResult(success=False, error=f"Binary file: {file_rel}")

    return resolved


def _select_lines(
    all_lines: list[str],
    start_line: int | None,
    end_line: int | None,
) -> tuple[list[str], int]:
    """Select a line range from all_lines, returning (selected, first_line_num)."""
    total = len(all_lines)
    if start_line is not None or end_line is not None:
        s = (start_line or 1) - 1  # convert to 0-indexed
        e = end_line or total
        s = max(0, min(s, total))
        e = max(s, min(e, total))
        return all_lines[s:e], s + 1
    return all_lines, 1


def _format_numbered(lines: list[str], first_line_num: int) -> str:
    """Format lines with line numbers."""
    return "\n".join(
        f"{first_line_num + i:4d}: {line.rstrip()}" for i, line in enumerate(lines)
    )


class ReadFileTool:
    """Read file content with optional line-range support.

    Returns file content with line numbers. Supports partial reads
    via ``start_line`` / ``end_line`` (1-indexed, inclusive).
    Registered as ``read_file`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Read file content with line numbers. Supports partial reads"
        " via start_line/end_line (1-indexed)."
        " Use for raw source when ast_inspect is insufficient."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "read_file"

    def execute(
        self,
        *,
        path: str = ".",
        file: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Read a file, optionally restricting to a line range.

        Args:
            path: Project root directory.
            file: Relative path to the file to read.
            start_line: Optional 1-indexed start line (inclusive).
            end_line: Optional 1-indexed end line (inclusive).

        Returns:
            ToolResult with file content, line numbers, and metadata.
        """
        root_str = path
        file_rel = file

        if not file_rel:
            return ToolResult(success=False, error="Missing required argument: file")

        # Resolve and validate file path
        result = _resolve_file(root_str, file_rel)
        if isinstance(result, ToolResult):
            return result
        resolved = result

        # Validate line range
        range_error = _validate_line_range(start_line, end_line)
        if range_error:
            return ToolResult(success=False, error=range_error)

        # Read content
        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"Cannot decode file as UTF-8: {file_rel}",
            )

        all_lines = text.splitlines(keepends=True)
        selected, first_line_num = _select_lines(all_lines, start_line, end_line)
        content = _format_numbered(selected, first_line_num)

        logger.debug("read %s: %d/%d lines", file_rel, len(selected), len(all_lines))

        return ToolResult(
            success=True,
            data={
                "content": content,
                "file": file_rel,
                "total_lines": len(all_lines),
                "showing": {
                    "start": first_line_num,
                    "end": first_line_num + len(selected) - 1,
                    "count": len(selected),
                },
            },
        )
