"""AuditTool — code quality audit as an AXMTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["AuditTool"]


class AuditTool(AXMTool):
    """Audit a project's code quality against the AXM standard.

    Registered as ``audit`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "audit"

    def execute(
        self,
        *,
        path: str = ".",
        category: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Audit a Python project's code quality.

        Args:
            path: Path to project root.
            category: Optional category filter.

        Returns:
            ToolResult with audit scores and details.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_audit.core.auditor import audit_project
            from axm_audit.formatters import format_agent

            result = audit_project(project_path, category=category)
            return ToolResult(success=True, data=format_agent(result))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
