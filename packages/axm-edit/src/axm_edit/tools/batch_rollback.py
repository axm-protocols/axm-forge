"""BatchRollbackTool — restore project state to a checkpoint.

Registered as ``batch_rollback`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

from axm_edit.core.checkpoint import rollback


class BatchRollbackTool:
    """Restore project state to a previous checkpoint.

    Registered as ``batch_rollback`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_rollback"

    def execute(self, **kwargs: Any) -> ToolResult:
        """Rollback to a checkpoint created by batch_edit.

        Args:
            **kwargs: Keyword arguments.
                path: Project root directory.
                checkpoint: The stash SHA from batch_edit's response.

        Returns:
            ToolResult indicating whether the rollback succeeded.
        """
        path: str = kwargs.get("path", ".")
        checkpoint: str | None = kwargs.get("checkpoint")

        if not checkpoint:
            return ToolResult(
                success=False,
                error="checkpoint is required",
            )

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            success = rollback(root, checkpoint)
            return ToolResult(
                success=success,
                data={"restored": success},
                error=None if success else "Rollback failed",
            )
        except (OSError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc))
