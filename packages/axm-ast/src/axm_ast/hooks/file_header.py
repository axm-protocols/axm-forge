"""FileHeaderHook — file header extraction for protocol briefings.

Protocol hook that extracts the first ~30 lines of source files referenced
by ``source_body`` results, providing import blocks, ``__all__``, and
``TYPE_CHECKING`` context without requiring a full ``Read``.  Registered
as ``ast:file-header`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["FileHeaderHook"]

_MAX_HEADER_LINES = 30


class _HeaderEntry(TypedDict):
    """Single ``{file, header}`` entry returned in ``headers`` metadata."""

    file: str
    header: str


def _extract_files_from_source_body(source_body: dict[str, object]) -> list[str]:
    """Extract file paths from source_body metadata."""
    files = source_body.get("files")
    if not files:
        return []
    if isinstance(files, str):
        return [files]
    if isinstance(files, Iterable):
        return [str(f) for f in files]
    return []


def _resolve_working_dir(
    params: dict[str, object],
    context: dict[str, object],
) -> Path:
    """Resolve the working directory from params or context."""
    raw_path = params.get("path") or context.get("working_dir", ".")
    if not isinstance(raw_path, (str, Path)):
        return Path(".").resolve()
    return Path(raw_path).resolve()


def _parse_file_list(
    params: dict[str, object],
    context: dict[str, object],
) -> list[str] | None:
    """Parse and deduplicate the file list from params or source_body.

    Returns ``None`` when no files can be determined (caller should
    return an empty result).
    """
    raw_files = params.get("files")
    files: list[str]
    if raw_files is None:
        source_body = context.get("source_body")
        if not isinstance(source_body, dict):
            return None
        files = _extract_files_from_source_body(source_body)
        if not files:
            return None
    elif isinstance(raw_files, str):
        files = [f.strip() for f in raw_files.splitlines() if f.strip()]
    elif isinstance(raw_files, Iterable):
        files = [str(f) for f in raw_files]
    else:
        return None

    return list(dict.fromkeys(files))


def _extract_single_header(
    working_dir: Path,
    file: str,
) -> _HeaderEntry | None:
    """Read the header of a single file, returning ``None`` on skip."""
    file_path = working_dir / file
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        logger.warning("Skipping binary file: %s", file)
        return None

    lines = text.splitlines(keepends=True)
    header = "".join(lines[:_MAX_HEADER_LINES])
    return {"file": file, "header": header}


class FileHeaderHook:
    """Extract the first ~30 lines of source files.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``files`` from *params*.  When *files* is not provided,
    extracts file paths from ``source_body`` in context.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``files`` (newline-separated paths or list).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with ``headers`` list in metadata on success.
        """
        working_dir = _resolve_working_dir(params, context)
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        unique_files = _parse_file_list(params, context)
        if unique_files is None:
            return HookResult.ok(headers=[])

        headers = [
            entry
            for file in unique_files
            if (entry := _extract_single_header(working_dir, file)) is not None
        ]
        return HookResult.ok(headers=headers)
