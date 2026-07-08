"""EditFileTool — find-and-replace text in a file.

Registered as ``edit_file`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path

from axm.tools.base import ToolResult

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
        "Find-and-replace in a file. Args: path, old, new."
        " Replaces first occurrence. Errors if text not found"
        " or ambiguous (multiple matches)."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "edit_file"

    @staticmethod
    def _validate_args(
        path: str | None, old: str | None, new: str | None, count: int
    ) -> str | None:
        """Return an error message if required args are invalid, else None."""
        if not path:
            return "Missing required argument: path"
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

    def execute(
        self,
        *,
        path: str | None = None,
        old: str | None = None,
        new: str | None = None,
        count: int = 1,
        **kwargs: object,
    ) -> ToolResult:
        """Find and replace text in a file.

        Args:
            path: Absolute path to the file to edit.
            old: Text to find (exact match).
            new: Replacement text.
            count: Max replacements (default 1). Use -1 for all.

        Returns:
            ToolResult with replacement details.
        """
        file_path = path

        validation_error = self._validate_args(file_path, old, new, count)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        # After validation, path/old/new are guaranteed non-None
        assert file_path is not None
        assert old is not None
        assert new is not None

        target = Path(file_path)

        if not target.is_file():
            return ToolResult(success=False, error=f"File not found: {file_path}")

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
            file_path,
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
