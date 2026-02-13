"""InitScaffoldTool — project scaffolding as an AXMTool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["InitScaffoldTool"]


class InitScaffoldTool(AXMTool):
    """Initialize a new Python project with best practices.

    Registered as ``init_scaffold`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_scaffold"

    def execute(
        self,
        *,
        path: str = ".",
        name: str | None = None,
        org: str = "",
        author: str = "",
        email: str = "",
        license: str = "MIT",
        description: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Initialize a new Python project.

        Args:
            path: Path to initialize project.
            name: Project name (defaults to directory name).
            org: GitHub org or username.
            author: Author name.
            email: Author email.
            license: License type.
            description: Project description.

        Returns:
            ToolResult with created files list.
        """
        if not org or not author or not email:
            return ToolResult(
                success=False,
                error="org, author, and email are required",
            )

        try:
            target_path = Path(path).resolve()
            project_name = name or target_path.name

            from axm_init.adapters.copier import CopierAdapter, CopierConfig
            from axm_init.core.templates import get_template_path

            copier_adapter = CopierAdapter()
            copier_config = CopierConfig(
                template_path=get_template_path(),
                destination=target_path,
                data={
                    "package_name": project_name,
                    "description": description or "A modern Python package",
                    "org": org,
                    "license": license,
                    "license_holder": org,
                    "author_name": author,
                    "author_email": email,
                },
            )
            result = copier_adapter.copy(copier_config)

            return ToolResult(
                success=result.success,
                data={
                    "project_name": project_name,
                    "files": [str(f) for f in result.files_created],
                },
                error=None if result.success else result.message,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
