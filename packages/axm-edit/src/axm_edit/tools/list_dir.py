"""ListDirTool — directory listing with file metadata.

Registered as ``list_dir`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

from axm_edit.core.engine import _resolve_safe

__all__ = ["ListDirTool"]

_MAX_ENTRIES = 200
_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".tox",
        ".eggs",
    }
)


def _should_skip(name: str) -> bool:
    """Return ``True`` if *name* should be excluded from listings."""
    return name.startswith(".") or name in _SKIP_NAMES


def _file_size(path: Path) -> int | None:
    """Return the file size in bytes, or ``None`` on error."""
    try:
        return path.stat().st_size
    except OSError:
        return None


def _collect_entries(
    root: Path,
    target: Path,
    max_depth: int,
    current_depth: int,
    entries: list[dict[str, Any]],
) -> bool:
    """Recursively collect directory entries up to *max_depth*.

    Entries are appended to *entries* in alphabetical order.
    Returns ``True`` if the cap was reached.
    """
    try:
        children = sorted(target.iterdir(), key=lambda p: p.name)
    except PermissionError:
        return False

    for child in children:
        if len(entries) >= _MAX_ENTRIES:
            return True

        name = child.name
        if _should_skip(name):
            continue

        rel = child.relative_to(root)
        # Sandboxing: ensure symlinks don't escape the root
        if _resolve_safe(root, str(rel)) is None:
            continue

        if child.is_dir():
            entries.append(
                {"name": name, "path": str(rel), "type": "dir", "size_bytes": None}
            )
            if current_depth < max_depth:
                if _collect_entries(root, child, max_depth, current_depth + 1, entries):
                    return True
        else:
            entries.append(
                {
                    "name": name,
                    "path": str(rel),
                    "type": "file",
                    "size_bytes": _file_size(child),
                }
            )

    return len(entries) >= _MAX_ENTRIES


class ListDirTool:
    """Directory listing with file metadata for AI agents.

    Lists files and directories within a sandboxed root directory.
    Supports recursive listing via *max_depth*. Hidden entries and
    build artefacts (``__pycache__``, ``node_modules``, etc.) are
    skipped automatically.
    Registered as ``list_dir`` via axm.tools entry point.
    """

    agent_hint: str = (
        "List directory tree with file sizes."
        " Use max_depth to limit. Replaces ls/find for project exploration."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "list_dir"

    def execute(
        self,
        *,
        path: str = ".",
        max_depth: int = 1,
        **kwargs: Any,
    ) -> ToolResult:
        """List files and directories in a project directory.

        Args:
            path: Root directory to list (default ".").
            max_depth: Recursion depth — 1 for immediate children
                only, >1 for nested listing (default 1).

        Returns:
            ToolResult with entries list (name, path, type,
            size_bytes), count, and truncated flag.
        """
        root_str = path
        depth = max(max_depth, 1)

        root = Path(root_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False,
                error=f"Path is not a directory: {root_str}",
            )

        entries: list[dict[str, Any]] = []
        truncated = _collect_entries(root, root, depth, 1, entries)

        return ToolResult(
            success=True,
            data={
                "entries": entries,
                "count": len(entries),
                "truncated": truncated,
            },
        )
