"""FlowsTool — execution flow tracing with entry point detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["FlowsTool"]


class FlowsTool(AXMTool):
    """Trace execution flows and detect entry points in a Python package.

    Registered as ``ast_flows`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_flows"

    def execute(
        self, *, path: str = ".", entry: str | None = None, **kwargs: Any
    ) -> ToolResult:
        """Detect entry points or trace flows from a symbol.

        Without ``entry``: returns detected entry points.
        With ``entry``: traces BFS flow from that entry point.

        Args:
            path: Path to package directory.
            entry: Optional entry point name to trace from.

        Returns:
            ToolResult with entry points or flow steps.
        """
        try:
            pkg_path = Path(path).resolve()
            if not pkg_path.is_dir():
                return ToolResult(success=False, error=f"Not a directory: {pkg_path}")

            from axm_ast.core.cache import get_package
            from axm_ast.core.flows import find_entry_points, trace_flow

            pkg = get_package(pkg_path)

            if entry is not None:
                max_depth = int(kwargs.get("max_depth", 5))
                steps = trace_flow(pkg, entry, max_depth=max_depth)
                return ToolResult(
                    success=True,
                    data={
                        "entry": entry,
                        "steps": [
                            {
                                "name": s.name,
                                "module": s.module,
                                "line": s.line,
                                "depth": s.depth,
                                "chain": s.chain,
                            }
                            for s in steps
                        ],
                        "depth": max_depth,
                        "count": len(steps),
                    },
                    hint="Tip: Use ast_impact(symbol) on key nodes for blast radius.",
                )

            entries = find_entry_points(pkg)
            return ToolResult(
                success=True,
                data={
                    "entry_points": [
                        {
                            "name": e.name,
                            "module": e.module,
                            "kind": e.kind,
                            "line": e.line,
                            "framework": e.framework,
                        }
                        for e in entries
                    ],
                    "count": len(entries),
                },
                hint="Tip: Use ast_flows(entry='<name>') to trace a flow.",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
