"""DescribeTool — full API surface dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.services.tools.base import AXMTool, ToolResult

__all__ = ["DescribeTool"]


class DescribeTool(AXMTool):
    """Describe a package: signatures, docstrings, __all__.

    Registered as ``ast_describe`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_describe"

    def execute(
        self, *, path: str = ".", compress: bool = False, **kwargs: Any
    ) -> ToolResult:
        """Describe a Python package.

        Args:
            path: Path to package directory.
            compress: If True, return compressed AI-friendly view.

        Returns:
            ToolResult with module descriptions.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.analyzer import analyze_package
            from axm_ast.formatters import format_compressed, format_json

            pkg = analyze_package(project_path)

            if compress:
                text = format_compressed(pkg)
                return ToolResult(
                    success=True,
                    data={
                        "compressed": text,
                        "module_count": len(pkg.modules),
                    },
                )

            data = format_json(pkg)
            return ToolResult(
                success=True,
                data={
                    "modules": data["modules"],
                    "module_count": len(pkg.modules),
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
