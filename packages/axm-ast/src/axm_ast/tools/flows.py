"""FlowsTool — execution flow tracing with entry point detection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_ast.tools.flows_text import (
    render_compact_text,
    render_entry_points_text,
    render_source_text,
    render_trace_text,
)

logger = logging.getLogger(__name__)

__all__ = [
    "FlowsTool",
    "render_compact_text",
    "render_entry_points_text",
    "render_source_text",
    "render_trace_text",
]


class FlowsTool(AXMTool):
    """Trace execution flows and detect entry points in a Python package.

    Registered as ``ast_flows`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_flows"

    def execute(  # noqa: PLR0913
        self,
        *,
        path: str = ".",
        entry: str | None = None,
        max_depth: int = 5,
        cross_module: bool = False,
        detail: str = "trace",
        exclude_stdlib: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Detect entry points or trace flows from a symbol.

        Without ``entry``: returns detected entry points.
        With ``entry``: traces BFS flow from that entry point.

        Args:
            path: Path to package directory.
            entry: Optional entry point name to trace from.
            max_depth: Maximum BFS depth for flow tracing.
            cross_module: Resolve imports and trace into external modules.
            detail: Level of detail — ``"trace"`` (default),
                ``"source"`` (includes function source code), or
                ``"compact"`` (tree-formatted string with
                box-drawing characters).
            exclude_stdlib: If False, include stdlib/builtin callees
                in the BFS trace.  Default True (exclude them).

        Returns:
            ToolResult with entry points or flow steps.  When tracing,
            ``data`` includes ``depth`` (actual max depth reached),
            ``count``, and ``truncated`` (True when frontier nodes at
            ``max_depth`` had unexpanded children).
            Returns ``success=False`` when the entry symbol is not found
            in the package.
        """
        try:
            pkg_path = Path(path).resolve()
            if not pkg_path.is_dir():
                return ToolResult(success=False, error=f"Not a directory: {pkg_path}")

            from axm_ast.core.cache import get_package
            from axm_ast.core.flows import (
                VALID_DETAILS,
                find_entry_points,
                format_flow_compact,
                trace_flow,
            )

            if detail not in VALID_DETAILS:
                return ToolResult(
                    success=False,
                    error=(
                        f"Invalid detail={detail!r};"
                        f" must be one of {sorted(VALID_DETAILS)}"
                    ),
                )

            pkg = get_package(pkg_path)

            if entry is not None:
                steps, truncated = trace_flow(
                    pkg,
                    entry,
                    max_depth=max_depth,
                    cross_module=cross_module,
                    detail=detail,
                    exclude_stdlib=exclude_stdlib,
                )
                actual_depth = max((s.depth for s in steps), default=0)
                if detail == "compact":
                    compact = format_flow_compact(steps)
                    data = {
                        "entry": entry,
                        "compact": compact,
                        "traces": compact,
                        "depth": actual_depth,
                        "cross_module": cross_module,
                        "count": len(steps),
                        "truncated": truncated,
                    }
                    return ToolResult(
                        success=True,
                        data=data,
                        text=render_compact_text(
                            entry=entry,
                            compact=compact,
                            depth=actual_depth,
                            cross_module=cross_module,
                            count=len(steps),
                            truncated=truncated,
                        ),
                    )

                step_dicts = []
                for s in steps:
                    d: dict[str, object] = {
                        "name": s.name,
                        "module": s.module,
                        "line": s.line,
                        "depth": s.depth,
                        "chain": s.chain,
                    }
                    if s.resolved_module is not None:
                        d["resolved_module"] = s.resolved_module
                    if s.source is not None:
                        d["source"] = s.source
                    step_dicts.append(d)
                data = {
                    "entry": entry,
                    "steps": step_dicts,
                    "depth": actual_depth,
                    "cross_module": cross_module,
                    "count": len(steps),
                    "truncated": truncated,
                }
                renderer = (
                    render_source_text if detail == "source" else render_trace_text
                )
                return ToolResult(
                    success=True,
                    data=data,
                    text=renderer(
                        entry=entry,
                        steps=step_dicts,
                        depth=actual_depth,
                        cross_module=cross_module,
                        count=len(steps),
                        truncated=truncated,
                    ),
                )

            entries = find_entry_points(pkg)
            entry_dicts = [
                {
                    "name": e.name,
                    "module": e.module,
                    "kind": e.kind,
                    "line": e.line,
                    "framework": e.framework,
                }
                for e in entries
            ]
            return ToolResult(
                success=True,
                data={
                    "entry_points": entry_dicts,
                    "count": len(entries),
                },
                text=render_entry_points_text(entry_dicts, count=len(entries)),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
