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
            if self._detect_workspace(project_path):
                return self._execute_workspace(project_path, format=format)
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )
            return self._execute_package(project_path, format=format)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _detect_workspace(self, project_path: Path) -> bool:
        """Return True if *project_path* is a uv workspace root."""
        from axm_ast.core.workspace import detect_workspace

        return detect_workspace(project_path) is not None

    def _execute_workspace(self, project_path: Path, *, format: str) -> ToolResult:
        """Build inter-package dependency graph for a uv workspace."""
        from axm_ast.core.workspace import (
            analyze_workspace,
            build_workspace_dep_graph,
            format_workspace_graph_mermaid,
        )

        ws = analyze_workspace(project_path)
        graph = build_workspace_dep_graph(ws)
        packages = ws.packages if hasattr(ws, "packages") else []
        nodes = [pkg.name if hasattr(pkg, "name") else str(pkg) for pkg in packages]
        ws_name = project_path.name

        mermaid_str = None
        if format == "mermaid":
            mermaid_str = format_workspace_graph_mermaid(ws)

        text = self._render_ws_text(
            ws_name=ws_name, graph=graph, mermaid_str=mermaid_str
        )
        data: dict[str, Any] = {"graph": graph, "nodes": nodes}

        if format == "mermaid":
            data["mermaid"] = mermaid_str
        elif format == "text":
            data["text"] = self._format_text(nodes, graph)

        return ToolResult(success=True, data=data, text=text)

    def _execute_package(self, project_path: Path, *, format: str) -> ToolResult:
        """Build intra-package import graph for a single package."""
        from axm_ast.core.analyzer import build_import_graph, module_dotted_name
        from axm_ast.core.cache import get_package
        from axm_ast.formatters import format_mermaid

        pkg = get_package(project_path)
        graph = build_import_graph(pkg)
        nodes = [module_dotted_name(mod.path, pkg.root) for mod in pkg.modules]
        data: dict[str, Any] = {"graph": graph, "nodes": nodes}

        mermaid_str = None
        if format == "mermaid":
            mermaid_str = format_mermaid(pkg)
            data["mermaid"] = mermaid_str
        elif format == "text":
            data["text"] = self._format_text(nodes, graph)

        pkg_name = getattr(pkg, "name", project_path.name)
        text = self._render_pkg_text(
            pkg_name=pkg_name,
            nodes=nodes,
            graph=graph,
            mermaid_str=mermaid_str,
        )
        return ToolResult(success=True, data=data, text=text)

    @staticmethod
    def _render_pkg_text(
        pkg_name: str,
        nodes: list[str],
        graph: dict[str, list[str]],
        mermaid_str: str | None,
    ) -> str:
        """Render package graph as compact text for LLM consumption."""
        edge_count = sum(len(v) for v in graph.values())
        mod_label = "module" if len(nodes) == 1 else "modules"
        header = (
            f"ast_graph | {pkg_name}"
            f" | {len(nodes)} {mod_label} \u00b7 {edge_count} edges"
        )
        lines = [header]

        # Tree-grouped modules: group by first dot-segment
        groups: dict[str, list[str]] = {}
        standalone: list[str] = []
        for name in nodes:
            parts = name.split(".", 1)
            if "." in name:
                groups.setdefault(parts[0], []).append(parts[1])
            else:
                standalone.append(name)

        lines.append("Modules:")
        for name in standalone:
            lines.append(f"  {name}")
        for prefix, children in groups.items():
            lines.append(f"  {prefix}: {' '.join(children)}")

        # Edges section — omit when empty
        if graph:
            lines.append("Edges:")
            for src, targets in graph.items():
                lines.append(f"  {src} \u2192 {', '.join(targets)}")

        # Mermaid appendix — suppress when zero edges
        if mermaid_str and graph:
            lines.append("")
            lines.append("```mermaid")
            lines.append(mermaid_str)
            lines.append("```")

        return "\n".join(lines)

    @staticmethod
    def _render_ws_text(
        ws_name: str,
        graph: dict[str, list[str]],
        mermaid_str: str | None,
    ) -> str:
        """Render workspace graph as compact text for LLM consumption."""
        all_pkgs: set[str] = set()
        for src, targets in graph.items():
            all_pkgs.add(src)
            all_pkgs.update(targets)
        edge_count = sum(len(v) for v in graph.values())
        header = (
            f"ast_graph | {ws_name} workspace"
            f" | {len(all_pkgs)} packages \u00b7 {edge_count} edges"
        )
        lines = [header]

        if graph:
            lines.append("Dependencies:")
            for src, targets in graph.items():
                lines.append(f"  {src} \u2192 {', '.join(targets)}")

        if mermaid_str:
            lines.append("")
            lines.append("```mermaid")
            lines.append(mermaid_str)
            lines.append("```")

        return "\n".join(lines)

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
