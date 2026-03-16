"""CallersTool — find call-sites of a symbol."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["CallersTool"]


class CallersTool(AXMTool):
    """Find all call-sites of a function via tree-sitter.

    Registered as ``ast_callers`` via axm.tools entry point.
    Workspace-aware: if path is a uv workspace root, searches
    across all member packages.
    """

    agent_hint: str = (
        "Find all call-sites of a symbol"
        " — precise caller list with file, line, and enclosing function."
        " Not grep noise."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_callers"

    def execute(
        self, *, path: str = ".", symbol: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Find all callers of a symbol.

        Args:
            path: Path to package or workspace directory.
            symbol: Symbol name to search for (required).

        Returns:
            ToolResult with caller list.
        """
        if not symbol:
            return ToolResult(success=False, error="symbol parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.workspace import detect_workspace

            ws = detect_workspace(project_path)
            if ws is not None:
                from axm_ast.core.callers import find_callers_workspace
                from axm_ast.core.workspace import analyze_workspace

                ws = analyze_workspace(project_path)
                callers = find_callers_workspace(ws, symbol)
            else:
                from axm_ast.core.cache import get_package
                from axm_ast.core.callers import find_callers

                pkg = get_package(project_path)
                callers = find_callers(pkg, symbol)

            caller_data = [
                {
                    "module": c.module,
                    "line": c.line,
                    "context": c.context,
                    "call_expression": c.call_expression,
                }
                for c in callers
            ]

            return ToolResult(
                success=True,
                data={"callers": caller_data, "count": len(caller_data)},
                hint=(
                    "Tip: Use ast_impact(symbol) for full blast radius including tests."
                ),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
