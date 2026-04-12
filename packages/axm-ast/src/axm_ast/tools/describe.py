"""DescribeTool — full API surface dump."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

from axm_ast.tools.describe_text import render_describe_text

logger = logging.getLogger(__name__)

__all__ = ["DescribeTool"]


class DescribeTool(AXMTool):
    """Describe a package: signatures, docstrings, __all__.

    Registered as ``ast_describe`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Show module API: signatures, docstrings, classes, __all__."
        " Use detail=toc for overview, modules=[...] to filter."
        " Replaces 10+ view_file."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_describe"

    def execute(
        self,
        *,
        path: str = ".",
        compress: bool = False,
        detail: str = "summary",
        modules: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Describe a Python package.

        Args:
            path: Path to package directory.
            compress: If True, return compressed AI-friendly view.
                Mutually exclusive with ``detail`` values other than
                the default (``summary``).  Passing both ``compress=True``
                and an explicit ``detail`` returns an error.
            detail: Detail level — ``toc`` (names + counts only),
                ``summary`` (signatures only),
                or ``detailed`` (+ docstrings, params, return types).
                Defaults to ``summary`` (signatures only, no docstrings).
            modules: Optional list of module name substrings to filter.
                Case-insensitive.  ``None`` or empty returns all modules.

        Returns:
            ToolResult with module descriptions.
        """
        if detail == "full":
            return ToolResult(
                success=False,
                error=(
                    "detail='full' has been removed — it crashes MCP transport "
                    "on large packages. Use detail='detailed' for docstrings and "
                    "params, or ast_inspect(source=true) for full symbol source."
                ),
            )

        if compress and detail != "summary":
            return ToolResult(
                success=False,
                error=(
                    f"compress=True and detail={detail!r} are mutually exclusive. "
                    "Use compress=True alone (implies its own format) "
                    f"or detail={detail!r} without compress."
                ),
            )

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
                result_data = {
                    "modules": toc,
                    "module_count": len(toc),
                }
                result_text = render_describe_text(result_data, "toc")
            elif compress:
                text = format_compressed(pkg)
                result_data = {
                    "compressed": text,
                    "module_count": len(pkg.modules),
                }
                result_text = text
            else:
                data = format_json(pkg, detail=detail)
                result_data = {
                    "modules": data["modules"],
                    "module_count": len(pkg.modules),
                }
                result_text = render_describe_text(result_data, detail)

            return ToolResult(success=True, data=result_data, text=result_text)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
