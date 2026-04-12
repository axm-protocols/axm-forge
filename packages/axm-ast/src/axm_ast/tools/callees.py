"""CalleesTool — find functions called by a symbol."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["CalleesTool"]


class CalleesTool(AXMTool):
    """Find all functions/methods called by a given symbol.

    Registered as ``ast_callees`` via axm.tools entry point.
    This is the inverse of ``ast_callers``: given a function name,
    returns all call-sites *within* that function body.
    """

    agent_hint: str = (
        "Find all functions called by a symbol"
        " — the inverse of ast_callers."
        " Returns call-sites with symbol, module, line."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_callees"

    def execute(
        self, *, path: str = ".", symbol: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Find all callees of a symbol.

        Args:
            path: Path to package or workspace directory.
            symbol: Symbol name to search for (required).

        Returns:
            ToolResult with callee list.
        """
        if not symbol:
            return ToolResult(success=False, error="symbol parameter is required")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            try:
                from axm_ast.core.flows import find_callees_workspace
                from axm_ast.core.workspace import analyze_workspace

                ws = analyze_workspace(project_path)
                callees = find_callees_workspace(ws, symbol)
            except ValueError:
                from axm_ast.core.cache import get_package
                from axm_ast.core.flows import find_callees

                pkg = get_package(project_path)
                callees = find_callees(pkg, symbol)

            callee_data = [
                {
                    "module": c.module,
                    "symbol": c.symbol,
                    "line": c.line,
                    "call_expression": c.call_expression,
                }
                for c in callees
            ]

            return ToolResult(
                success=True,
                data={"callees": callee_data, "count": len(callee_data)},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
