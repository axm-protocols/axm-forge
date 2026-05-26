"""SearchFilesTool — grep-like search across project files.

Registered as ``search_files`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

from axm_edit.core.engine import _resolve_safe
from axm_edit.utils import is_binary

__all__ = ["SearchFilesTool"]

logger = logging.getLogger(__name__)

_MAX_RESULTS = 50
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "node_modules",
        ".tox",
        ".eggs",
    }
)


def _matches_include(filename: str, include: list[str]) -> bool:
    """Return True if *filename* matches at least one include glob."""
    return any(fnmatch.fnmatch(filename, pat) for pat in include)


def _search_file(
    file_path: Path,
    root: Path,
    matcher: re.Pattern[str] | str,
    is_regex: bool,
    results: list[dict[str, Any]],
) -> bool:
    """Search a single file, appending matches to *results*.

    Returns True if the cap has been reached.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    relative = str(file_path.relative_to(root))

    for line_num, line in enumerate(text.splitlines(), start=1):
        if len(results) >= _MAX_RESULTS:
            return True

        matched = False
        if is_regex:
            assert isinstance(matcher, re.Pattern)
            matched = matcher.search(line) is not None
        else:
            assert isinstance(matcher, str)
            matched = matcher in line

        if matched:
            results.append(
                {
                    "file": relative,
                    "line": line_num,
                    "content": line.rstrip(),
                }
            )

    return len(results) >= _MAX_RESULTS


def _walk_and_search(
    root: Path,
    matcher: re.Pattern[str] | str,
    is_regex: bool,
    include: list[str] | None,
) -> tuple[list[dict[str, Any]], bool]:
    """Walk the file tree and collect search matches.

    Returns ``(results, truncated)``.
    """
    results: list[dict[str, Any]] = []
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune hidden and excluded directories (in-place)
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        dirnames.sort()  # deterministic order

        for filename in sorted(filenames):
            if filename.startswith("."):
                continue

            if include and not _matches_include(filename, include):
                continue

            file_path = Path(dirpath) / filename

            # Sandboxing check
            resolved = _resolve_safe(root, str(file_path.relative_to(root)))
            if resolved is None:
                continue

            # Skip binary files
            if is_binary(file_path):
                continue

            if _search_file(file_path, root, matcher, is_regex, results):
                truncated = True
                break

        if truncated:
            break

    return results, truncated


class SearchFilesTool:
    """Grep-like search across project files.

    Searches for literal strings or regex patterns across files within a
    sandboxed project root. Supports glob-based file filtering.
    Registered as ``search_files`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Text or regex search across files."
        " Returns matching lines with file:line context."
        " Use when ast_search can't help (comments, strings, config)."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "search_files"

    def execute(
        self,
        *,
        path: str = ".",
        pattern: str | None = None,
        is_regex: bool = False,
        include: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Search for a pattern across project files.

        Args:
            path: Project root directory (default ".").
            pattern: Search string or regex (required).
            is_regex: Treat pattern as regex (default False).
            include: Glob patterns to filter files (e.g. ["*.py"]).

        Returns:
            ToolResult with matches list (file, line, content),
            count, and truncated flag.
        """
        root_str = path

        # ── Validate inputs ──────────────────────────────────────────
        if pattern is None or pattern == "":
            return ToolResult(
                success=False,
                error="Missing required argument: pattern",
            )

        root = Path(root_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False,
                error=f"Root is not a directory: {root_str}",
            )

        # Compile regex if needed
        matcher: re.Pattern[str] | str
        if is_regex:
            try:
                matcher = re.compile(pattern)
            except re.error as exc:
                return ToolResult(
                    success=False,
                    error=f"Invalid regex pattern: {exc}",
                )
        else:
            matcher = pattern

        # ── Walk and search ──────────────────────────────────────────
        results, truncated = _walk_and_search(root, matcher, is_regex, include)

        return ToolResult(
            success=True,
            data={
                "matches": results,
                "count": len(results),
                "truncated": truncated,
            },
        )
