"""CallersTool — find call-sites of a symbol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["CallersTool"]


class CallersTool(AXMTool):
    """Find all call-sites of a function via tree-sitter.

    Registered as ``ast_callers`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_callers"

    def execute(
        self, *, path: str = ".", symbol: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Find all callers of a symbol.

        Args:
            path: Path to package directory.
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

            from axm_ast.core.analyzer import analyze_package
            from axm_ast.core.callers import find_callers

            pkg = analyze_package(project_path)
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
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
