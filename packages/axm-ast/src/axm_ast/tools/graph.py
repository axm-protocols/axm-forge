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
                return self._execute_workspace(project_path, format=format)

            return self._execute_package(project_path, format=format)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _execute_workspace(self, project_path: Path, *, format: str) -> ToolResult:
        """Build inter-package dependency graph for a uv workspace."""
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
            )

        return ToolResult(success=True, data={"graph": graph})

    def _execute_package(self, project_path: Path, *, format: str) -> ToolResult:
        """Build intra-package import graph for a single package."""
        from axm_ast.core.analyzer import build_import_graph, module_dotted_name
        from axm_ast.core.cache import get_package
        from axm_ast.formatters import format_mermaid

        pkg = get_package(project_path)
        graph = build_import_graph(pkg)
        nodes = [module_dotted_name(mod.path, pkg.root) for mod in pkg.modules]
        data: dict[str, Any] = {"graph": graph, "nodes": nodes}

        if format == "mermaid":
            data["mermaid"] = format_mermaid(pkg)
        elif format == "text":
            data["text"] = self._format_text(nodes, graph)

        return ToolResult(success=True, data=data)

    @staticmethod
    def _format_text(nodes: list[str], graph: dict[str, list[str]]) -> str:
        """Render nodes and edges as a human-readable text block."""
        lines = ["Nodes:"]
        for name in nodes:
            lines.append(f"  {name}")
        lines.append("")
        lines.append("Edges:")
        for src, targets in graph.items():
            for target in targets:
                lines.append(f"  {src} -> {target}")
        return "\n".join(lines)
