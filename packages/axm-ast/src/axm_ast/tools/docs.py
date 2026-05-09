"""DocsTool — one-shot documentation tree dump."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from axm.tools.base import AXMTool, ToolResult

from axm_ast.core.docs import DocsResult
from axm_ast.tools._base import safe_execute

logger = logging.getLogger(__name__)

__all__ = ["DocsTool"]


class DocsTool(AXMTool):
    """Dump README + mkdocs + docs tree in one call.

    Registered as ``ast_docs`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "ast_docs"

    @safe_execute
    def execute(
        self,
        *,
        path: str = ".",
        detail: str = "full",
        pages: list[str] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Dump project documentation.

        Args:
            path: Project root directory.
            detail: Detail level — ``toc``, ``summary``, or ``full``.
            pages: Page name substrings to filter (case-insensitive).
            **kwargs: Reserved for future use.

        Returns:
            ToolResult with documentation data.
        """
        project_path = Path(path).resolve()
        if not project_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {project_path}")

        from axm_ast.core.docs import discover_docs, format_docs_json

        result: DocsResult = discover_docs(project_path, detail=detail, pages=pages)
        return ToolResult(
            success=True,
            data=cast("dict[str, object]", format_docs_json(result)),
        )
