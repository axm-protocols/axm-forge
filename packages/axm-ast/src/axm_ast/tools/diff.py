"""MCP tool for structural branch diff."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)


class DiffTool(AXMTool):
    """Compare two git refs at symbol level.

    Registered as ``ast_diff`` via axm.tools entry point.
    Uses git worktrees to avoid disturbing the working tree.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_diff"

    def execute(
        self,
        *,
        path: str = ".",
        base: str = "",
        head: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Compare two branches at symbol level.

        Args:
            path: Path to package directory.
            base: Base git ref (branch, tag, commit).
            head: Head git ref (branch, tag, commit).

        Returns:
            ToolResult with structural diff data.
        """
        if not base:
            return ToolResult(success=False, error="base parameter is required")
        if not head:
            return ToolResult(success=False, error="head parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.structural_diff import structural_diff

            result = structural_diff(project_path, base, head)

            if "error" in result:
                return ToolResult(success=False, error=result["error"])

            return ToolResult(
                success=True,
                data=result,
                hint="Tip: Use ast_impact(symbol) on changed symbols to assess risk.",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
