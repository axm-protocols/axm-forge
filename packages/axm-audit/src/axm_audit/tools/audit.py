"""AuditTool — code quality audit as an AXMTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_audit.models.results import format_categories_help

__all__ = ["AuditTool"]


class AuditTool(AXMTool):
    """Audit a project's code quality against the AXM standard.

    Registered as ``audit`` via axm.tools entry point.

    Accepted ``category`` values (sourced from
    ``axm_audit.models.results.SCORED_CATEGORIES | EXTRA_NONSCORED_CATEGORIES``):

    {categories}
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
            category: Optional category filter. One of:
                {categories}

        Returns:
            ToolResult with audit scores and details (``data`` dict
            and a compact ``text`` summary for LLM consumption).
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_audit.core.auditor import audit_project
            from axm_audit.formatters import format_agent, format_agent_text

            result = audit_project(project_path, category=category)
            data = format_agent(result)
            text = format_agent_text(data, category=category)
            return ToolResult(success=True, data=data, text=text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))


_categories_block = format_categories_help()
_indented_block = "\n        ".join(_categories_block.splitlines())
if AuditTool.__doc__ is not None:
    AuditTool.__doc__ = AuditTool.__doc__.replace("{categories}", _categories_block)
if AuditTool.execute.__doc__ is not None:
    AuditTool.execute.__doc__ = AuditTool.execute.__doc__.replace(
        "{categories}", _indented_block
    )
