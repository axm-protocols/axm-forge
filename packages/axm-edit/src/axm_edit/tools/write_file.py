"""WriteFileTool — write content to a file.

Registered as ``write_file`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.utils import resolve_safe

__all__ = ["WriteFileTool"]

logger = logging.getLogger(__name__)


def render_text(*, path: str, byte_count: int) -> str:
    """Render a compact, ``git``-style LLM-facing view of a write result.

    The header carries the global status (``✓``) plus the written path and
    its exact byte count. Both values mirror ``data`` verbatim — only the
    JSON structure (braces, quotes, keys) is dropped, so no information is
    lost relative to ``data``.
    """
    plural = "s" if byte_count != 1 else ""
    return f"write_file | ✓ | {path} · {byte_count} byte{plural}"


class WriteFileTool:
    """Write content to a file, creating parent directories.

    Simple single-file write for AI agents. For atomic multi-file
    operations, use :class:`BatchEditTool` instead.
    Registered as ``write_file`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Write text content to a file (creates parents), confined to a"
        " project root. Args: path (root), file (relative), content."
        " For multi-file atomic edits, use batch_edit instead."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "write_file"

    def execute(
        self,
        *,
        path: str = ".",
        file: str | None = None,
        content: str | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Write content to a file, confined under a project root.

        Args:
            path: Project root directory (default ".").
            file: Path to the file to write, relative to ``path``.
            content: Text content to write.

        Returns:
            ToolResult with written file path and byte count. A ``file``
            that escapes ``path`` (absolute outside root, or ``..``
            traversal) is refused with ``success=False``.
        """
        root_str = path
        file_rel = file

        if not file_rel:
            return ToolResult(success=False, error="Missing required argument: file")
        if content is None:
            return ToolResult(success=False, error="Missing required argument: content")

        root = Path(root_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False,
                error=f"Root is not a directory: {root_str}",
            )

        target = resolve_safe(root, file_rel)
        if target is None:
            return ToolResult(
                success=False,
                error=f"Path escapes project root (confinement barrier): {file_rel}",
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"Write failed: {exc}")

        byte_count = len(content.encode("utf-8"))
        logger.debug("wrote %s (%d bytes)", file_rel, byte_count)

        target_path = str(target)
        return ToolResult(
            success=True,
            data={
                "path": target_path,
                "bytes": byte_count,
            },
            text=render_text(path=target_path, byte_count=byte_count),
        )
