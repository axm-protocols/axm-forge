"""EditFileTool — find-and-replace text in a file.

Registered as ``edit_file`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.utils import resolve_safe

__all__ = ["EditFileTool"]

logger = logging.getLogger(__name__)


def render_text(*, path: str, replacements: int, first_line: int) -> str:
    """Render a compact, ``git``-style LLM-facing view of an edit result.

    The header carries the global status (``✓``), the edited path, the exact
    number of replacements applied, and the 1-indexed line of the first
    match. All three values mirror ``data`` verbatim — only the JSON
    structure (braces, quotes, keys) is dropped, so no information is lost
    relative to ``data``. (The success path always applies at least one
    replacement; the no-match and ambiguous cases are surfaced earlier via
    ``error`` and never reach this renderer.)
    """
    plural = "s" if replacements != 1 else ""
    return (
        f"edit_file | ✓ | {path} · {replacements} replacement{plural} @ L{first_line}"
    )


class EditFileTool:
    """Find and replace text in a single file.

    Performs a single-occurrence replacement by default. Errors if
    the target text is not found or appears multiple times (unless
    ``count`` is specified).
    Registered as ``edit_file`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Find-and-replace in a file, confined to a project root."
        " Args: path (root), file (relative), old, new."
        " Replaces first occurrence. Errors if text not found"
        " or ambiguous (multiple matches)."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "edit_file"

    @staticmethod
    def _validate_args(
        file: str | None, old: str | None, new: str | None, count: int
    ) -> str | None:
        """Return an error message if required args are invalid, else None."""
        if not file:
            return "Missing required argument: file"
        if old is None:
            return "Missing required argument: old"
        if new is None:
            return "Missing required argument: new"
        if count != -1 and count < 1:
            return "count must be -1 (all) or a positive integer"
        return None

    @staticmethod
    def _check_occurrences(old: str, occurrences: int, count: int) -> str | None:
        """Return an error message if occurrence count is invalid, else None."""
        if occurrences == 0:
            return "Text not found in file"
        if occurrences > 1 and count == 1:
            return (
                f"Ambiguous: found {occurrences} occurrences. "
                f"Use count={occurrences} or count=-1 to replace all."
            )
        return None

    @staticmethod
    def _resolve_target(root_str: str, file_rel: str) -> Path | ToolResult:
        """Resolve *file_rel* under *root_str*, confined via ``resolve_safe``.

        Returns the resolved ``Path`` on success, or a ``ToolResult`` error
        when the root is not a directory, the target escapes the root, or the
        file does not exist.
        """
        root = Path(root_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False,
                error=f"Root is not a directory: {root_str}",
            )
        target = resolve_safe(root, file_rel)
        if target is None:
            return ToolResult(
                success=False,
                error=f"Path escapes project root (confinement barrier): {file_rel}",
            )
        if not target.is_file():
            return ToolResult(success=False, error=f"File not found: {file_rel}")
        return target

    def execute(
        self,
        *,
        path: str = ".",
        file: str | None = None,
        old: str | None = None,
        new: str | None = None,
        count: int = 1,
        **kwargs: object,
    ) -> ToolResult:
        """Find and replace text in a file, confined under a project root.

        Args:
            path: Project root directory (default ".").
            file: Path to the file to edit, relative to ``path``.
            old: Text to find (exact match).
            new: Replacement text.
            count: Max replacements (default 1). Use -1 for all.

        Returns:
            ToolResult with replacement details. A ``file`` that escapes
            ``path`` (absolute outside root, or ``..`` traversal) is
            refused with ``success=False``.
        """
        root_str = path
        file_rel = file

        validation_error = self._validate_args(file_rel, old, new, count)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        # After validation, file/old/new are guaranteed non-None
        assert file_rel is not None
        assert old is not None
        assert new is not None

        resolved = self._resolve_target(root_str, file_rel)
        if isinstance(resolved, ToolResult):
            return resolved
        target = resolved

        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(success=False, error=f"Read failed: {exc}")

        occurrences = content.count(old)
        occurrence_error = self._check_occurrences(old, occurrences, count)
        if occurrence_error:
            return ToolResult(success=False, error=occurrence_error)

        # Perform replacement
        if count == -1:
            new_content = content.replace(old, new)
            replaced = occurrences
        else:
            new_content = content.replace(old, new, count)
            replaced = min(count, occurrences)

        try:
            target.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"Write failed: {exc}")

        # Find line number of first occurrence
        line_num = content[: content.index(old)].count("\n") + 1

        logger.debug(
            "edit %s: replaced %d occurrence(s) at line %d",
            file_rel,
            replaced,
            line_num,
        )

        target_path = str(target)
        return ToolResult(
            success=True,
            data={
                "path": target_path,
                "replacements": replaced,
                "first_line": line_num,
            },
            text=render_text(
                path=target_path,
                replacements=replaced,
                first_line=line_num,
            ),
        )
