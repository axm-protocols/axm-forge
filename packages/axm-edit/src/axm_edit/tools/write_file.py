"""WriteFileTool — write content to a file.

Registered as ``write_file`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

__all__ = ["WriteFileTool"]

logger = logging.getLogger(__name__)


class WriteFileTool:
    """Write content to a file, creating parent directories.

    Simple single-file write for AI agents. For atomic multi-file
    operations, use :class:`BatchEditTool` instead.
    Registered as ``write_file`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Write text content to a file (creates parents)."
        " Use for artifacts, configs, and new files."
        " For multi-file atomic edits, use batch_edit instead."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "write_file"

    def execute(
        self,
        *,
        path: str | None = None,
        content: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Write content to a file.

        Args:
            path: Absolute path to the file to write.
            content: Text content to write.

        Returns:
            ToolResult with written file path and byte count.
        """
        file_path = path

        if not file_path:
            return ToolResult(success=False, error="Missing required argument: path")
        if content is None:
            return ToolResult(success=False, error="Missing required argument: content")

        target = Path(file_path)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"Write failed: {exc}")

        byte_count = len(content.encode("utf-8"))
        logger.debug("wrote %s (%d bytes)", file_path, byte_count)

        return ToolResult(
            success=True,
            data={
                "path": str(target),
                "bytes": byte_count,
            },
        )
