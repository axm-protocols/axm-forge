"""DescribeTool — full API surface dump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

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
        self,
        *,
        path: str = ".",
        compress: bool = False,
        detail: str = "detailed",
        modules: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Describe a Python package.

        Args:
            path: Path to package directory.
            compress: If True, return compressed AI-friendly view.
            detail: Detail level — ``toc`` (names + counts only),
                ``summary`` (signatures only),
                ``detailed`` (+ docstrings, params, return types),
                or ``full`` (+ line numbers, imports, variables).
                Defaults to ``detailed`` so docstrings are always included.
            modules: Optional list of module name substrings to filter.
                Case-insensitive.  ``None`` or empty returns all modules.

        Returns:
            ToolResult with module descriptions.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_ast.core.cache import get_package
            from axm_ast.formatters import (
                filter_modules,
                format_compressed,
                format_json,
                format_toc,
            )

            pkg = get_package(project_path)
            pkg = filter_modules(pkg, modules)

            if detail == "toc":
                toc = format_toc(pkg)
                return ToolResult(
                    success=True,
                    data={
                        "modules": toc,
                        "module_count": len(toc),
                    },
                    hint="Tip: Use ast_impact(symbol) before modifying any symbol.",
                )

            if compress:
                text = format_compressed(pkg)
                return ToolResult(
                    success=True,
                    data={
                        "compressed": text,
                        "module_count": len(pkg.modules),
                    },
                    hint="Tip: Use ast_impact(symbol) before modifying any symbol.",
                )

            data = format_json(pkg, detail=detail)
            return ToolResult(
                success=True,
                data={
                    "modules": data["modules"],
                    "module_count": len(pkg.modules),
                },
                hint="Tip: Use ast_impact(symbol) before modifying any symbol.",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
