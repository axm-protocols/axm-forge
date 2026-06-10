"""AstFileHeaderTool — extract the first lines of source files.

Returns the import block, ``__all__`` and ``TYPE_CHECKING`` context of one or
more files without a full read — the tool form of the legacy ``ast:file-header``
hook. Registered as ``ast_file_header`` via axm.tools entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_ast.tools.file_header_text import render_failure_text, render_text

logger = logging.getLogger(__name__)

__all__ = ["AstFileHeaderTool"]

_DEFAULT_MAX_LINES = 30


class AstFileHeaderTool(AXMTool):
    """Extract the first ``max_lines`` lines of one or more source files.

    Registered as ``ast_file_header`` via axm.tools entry point.
    """

    domain = "ast"
    tags = frozenset({"header", "imports", "source"})

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "ast_file_header"

    def execute(  # type: ignore[override]
        self,
        *,
        files: list[str],
        path: str = ".",
        max_lines: int = _DEFAULT_MAX_LINES,
        **kwargs: object,
    ) -> ToolResult:
        """Extract the header of each file in *files*.

        Args:
            files: File paths relative to *path* (required).
            path: Project root directory (default ``.``).
            max_lines: Number of leading lines to keep per file (default 30).

        Returns:
            ToolResult with a ``headers`` list of ``{file, header}`` entries.
            Files that are missing or binary are skipped.
        """
        working_dir = Path(path).resolve()
        if not working_dir.is_dir():
            error = f"path not a directory: {working_dir}"
            return ToolResult(
                success=False, error=error, text=render_failure_text(error=error)
            )

        unique_files = list(dict.fromkeys(files))
        headers = [
            entry
            for file in unique_files
            if (entry := _extract_header(working_dir, file, max_lines)) is not None
        ]
        data: dict[str, object] = {"headers": headers}
        return ToolResult(success=True, data=data, text=render_text(headers))


def _extract_header(
    working_dir: Path,
    file: str,
    max_lines: int,
) -> dict[str, str] | None:
    """Read the first *max_lines* lines of one file, or ``None`` on skip."""
    file_path = working_dir / file
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        logger.warning("Skipping binary file: %s", file)
        return None
    lines = text.splitlines(keepends=True)
    return {"file": file, "header": "".join(lines[:max_lines])}
