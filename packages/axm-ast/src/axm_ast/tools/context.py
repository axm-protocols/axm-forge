"""ContextTool — one-shot project context dump."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["ContextTool"]


class ContextTool(AXMTool):
    """One-shot project context: stack, patterns, module ranking.

    Registered as ``ast_context`` via axm.tools entry point.
    Workspace-aware: if path is a uv workspace root, returns
    workspace-level context with all packages.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_context"

    def execute(
        self,
        *,
        path: str = ".",
        depth: int | None = 1,
        slim: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Dump complete project context for AI agents.

        Args:
            path: Path to package or workspace directory.
            depth: Detail level (0=top-5, 1=sub-packages,
                2=modules, 3+=symbols, None=full).
            slim: If True, override depth to 0 for compact output.

        Returns:
            ToolResult with project context data.
        """
        if slim:
            depth = 0
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.workspace import detect_workspace

            ws = detect_workspace(project_path)
            if ws is not None:
                from axm_ast.core.workspace import (
                    build_workspace_context,
                    format_workspace_context,
                )

                ctx = build_workspace_context(project_path)
                return ToolResult(
                    success=True,
                    data=format_workspace_context(
                        ctx, depth=depth if depth is not None else 1
                    ),
                )

            from axm_ast.core.context import build_context, format_context_json

            ctx = build_context(project_path)
            return ToolResult(
                success=True,
                data=format_context_json(ctx, depth=depth),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
