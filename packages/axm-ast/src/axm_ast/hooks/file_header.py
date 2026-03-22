"""FileHeaderHook — file header extraction for protocol briefings.

Protocol hook that extracts the first ~30 lines of source files referenced
by ``source_body`` results, providing import blocks, ``__all__``, and
``TYPE_CHECKING`` context without requiring a full ``Read``.  Registered
as ``ast:file-header`` via ``axm.hooks`` entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

logger = logging.getLogger(__name__)

__all__ = ["FileHeaderHook"]

_MAX_HEADER_LINES = 30


def _extract_files_from_source_body(source_body: dict[str, Any]) -> list[str]:
    """Extract unique file paths from a source_body result."""
    symbols = source_body.get("symbols")
    if symbols is None:
        return []

    if isinstance(symbols, dict):
        symbols = [symbols]

    files: list[str] = []
    for sym in symbols:
        f = sym.get("file")
        if f and sym.get("body") is not None:
            files.append(f)
    return files


@dataclass
class FileHeaderHook:
    """Extract the first ~30 lines of source files.

    Reads ``path`` from *params* (or ``working_dir`` from context)
    and ``files`` from *params*.  When *files* is not provided,
    extracts file paths from ``source_body`` in context.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``files`` (newline-separated paths or list).
                Optional ``path`` (overrides ``working_dir`` from context).

        Returns:
            HookResult with ``headers`` list in metadata on success.
        """
        path = params.get("path") or context.get("working_dir", ".")
        working_dir = Path(path).resolve()
        if not working_dir.is_dir():
            return HookResult.fail(f"working_dir not a directory: {working_dir}")

        files = params.get("files")
        if files is None:
            source_body = context.get("source_body")
            if not source_body:
                return HookResult.ok(headers=[])
            files = _extract_files_from_source_body(source_body)

        if isinstance(files, str):
            files = [f.strip() for f in files.splitlines() if f.strip()]

        # Deduplicate preserving order
        unique_files = list(dict.fromkeys(files))

        headers: list[dict[str, str]] = []
        for file in unique_files:
            file_path = working_dir / file
            try:
                text = file_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            except UnicodeDecodeError:
                logger.warning("Skipping binary file: %s", file)
                continue

            lines = text.splitlines(keepends=True)
            header = "".join(lines[:_MAX_HEADER_LINES])
            headers.append({"file": file, "header": header})

        return HookResult.ok(headers=headers)
