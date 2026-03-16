"""GraphTool — import dependency graph."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

logger = logging.getLogger(__name__)

__all__ = ["GraphTool"]


class GraphTool(AXMTool):
    """Import dependency graph with text/mermaid/json output.

    Registered as ``ast_graph`` via axm.tools entry point.
    Workspace-aware: if path is a uv workspace root, returns
    inter-package dependency graph.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_graph"

    def execute(
        self, *, path: str = ".", format: str = "json", **kwargs: Any
    ) -> ToolResult:
        """Generate import dependency graph.

        Args:
            path: Path to package or workspace directory.
            format: Output format — 'json', 'mermaid', or 'text'.

        Returns:
            ToolResult with graph data.
        """
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
                    analyze_workspace,
                    build_workspace_dep_graph,
                    format_workspace_graph_mermaid,
                )

                ws = analyze_workspace(project_path)
                graph = build_workspace_dep_graph(ws)

                if format == "mermaid":
                    mermaid_str = format_workspace_graph_mermaid(ws)
                    return ToolResult(
                        success=True,
                        data={"mermaid": mermaid_str, "graph": graph},
                        hint=(
                            "Tip: Use ast_describe(modules=[...])"
                            " to explore specific modules."
                        ),
                    )

                return ToolResult(
                    success=True,
                    data={"graph": graph},
                    hint=(
                        "Tip: Use ast_describe(modules=[...])"
                        " to explore specific modules."
                    ),
                )

            from axm_ast.core.analyzer import build_import_graph
            from axm_ast.core.cache import get_package
            from axm_ast.formatters import format_mermaid

            pkg = get_package(project_path)
            graph = build_import_graph(pkg)

            if format == "mermaid":
                mermaid_str = format_mermaid(pkg)
                return ToolResult(
                    success=True,
                    data={"mermaid": mermaid_str, "graph": graph},
                    hint=(
                        "Tip: Use ast_describe(modules=[...])"
                        " to explore specific modules."
                    ),
                )

            return ToolResult(
                success=True,
                data={"graph": graph},
                hint=(
                    "Tip: Use ast_describe(modules=[...]) to explore specific modules."
                ),
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
