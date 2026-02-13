"""GraphTool — import dependency graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["GraphTool"]


class GraphTool(AXMTool):
    """Import dependency graph with text/mermaid/json output.

    Registered as ``ast_graph`` via axm.tools entry point.
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
            path: Path to package directory.
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

            from axm_ast.core.analyzer import analyze_package, build_import_graph
            from axm_ast.formatters import format_mermaid

            pkg = analyze_package(project_path)
            graph = build_import_graph(pkg)

            if format == "mermaid":
                mermaid_str = format_mermaid(pkg)
                return ToolResult(
                    success=True,
                    data={"mermaid": mermaid_str, "graph": graph},
                )

            return ToolResult(
                success=True,
                data={"graph": graph},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
