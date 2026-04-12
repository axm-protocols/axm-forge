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
        **kwargs: Any,
    ) -> ToolResult:
        """Dump complete project context for AI agents.

        Args:
            path: Path to package or workspace directory.
            depth: Detail level (0=top-5, 1=sub-packages,
                2=modules, 3+=symbols, None=full).

        Returns:
            ToolResult with project context data.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            try:
                from axm_ast.core.workspace import (
                    build_workspace_context,
                    format_workspace_context,
                    format_workspace_text,
                )

                ctx = build_workspace_context(project_path)
                formatted = format_workspace_context(
                    ctx, depth=depth if depth is not None else 1
                )
                return ToolResult(
                    success=True,
                    data=formatted,
                    text=format_workspace_text(formatted),
                )
            except ValueError:
                pass

            from axm_ast.core.context import (
                build_context,
                format_context_json,
                format_context_text,
            )

            ctx = build_context(project_path)
            formatted = format_context_json(ctx, depth=depth)
            try:
                text = format_context_text(
                    formatted, depth=depth if depth is not None else 0
                )
            except (KeyError, TypeError):
                text = None
            return ToolResult(
                success=True,
                data=formatted,
                text=text,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
