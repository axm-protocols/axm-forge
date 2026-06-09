"""ListDirTool — directory listing with file metadata.

Registered as ``list_dir`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.engine import _resolve_safe

__all__ = ["ListDirTool"]

_MAX_ENTRIES = 200
_BYTES_PER_UNIT = 1024
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


def _is_included(root: Path, child: Path) -> bool:
    if _should_skip(child.name):
        return False
    # Sandboxing: ensure symlinks don't escape the root
    return _resolve_safe(root, str(child.relative_to(root))) is not None


def _entry_for(root: Path, child: Path) -> dict[str, object]:
    rel = str(child.relative_to(root))
    if child.is_dir():
        return {"name": child.name, "path": rel, "type": "dir", "size_bytes": None}
    return {
        "name": child.name,
        "path": rel,
        "type": "file",
        "size_bytes": _file_size(child),
    }


def _human_size(n: int | None) -> str:
    """Render a byte count as a compact human-readable string (e.g. ``30.9K``).

    Returns an empty string for ``None`` (size unavailable / directories).
    """
    if n is None:
        return ""
    units = ("B", "K", "M", "G", "T")
    value = float(n)
    idx = 0
    while value >= _BYTES_PER_UNIT and idx < len(units) - 1:
        value /= _BYTES_PER_UNIT
        idx += 1
    if idx == 0:
        return f"{int(value)}B"
    return f"{value:.1f}{units[idx]}"


def render_text(
    *,
    entries: list[dict[str, object]],
    count: int,
    truncated: bool,
) -> str:
    """Render a compact, ``ls``-style LLM-facing view of the listing.

    One entry per line, using the relative ``path`` (which subsumes ``name``
    and encodes the directory hierarchy when ``max_depth`` > 1). Directories
    get a trailing ``/``; files carry a compact human-readable size. The
    header carries the total entry count, the dir/file split, and an explicit
    ``TRUNCATED`` flag when the entry cap was reached. Every entry (path,
    type, size) and the truncation signal are preserved verbatim, so no
    information is lost relative to ``data``.
    """
    if not entries:
        return "list_dir | 0 entries"

    n_dirs = sum(1 for e in entries if e["type"] == "dir")
    n_files = count - n_dirs
    plural_d = "s" if n_dirs != 1 else ""
    plural_f = "s" if n_files != 1 else ""
    header = (
        f"list_dir | {count} entries"
        f" · {n_dirs} dir{plural_d} · {n_files} file{plural_f}"
    )
    if truncated:
        header += f" · TRUNCATED at {count}"

    lines = [header]
    for entry in entries:
        path = str(entry["path"])
        if entry["type"] == "dir":
            lines.append(f"{path}/")
            continue
        size_raw = entry.get("size_bytes")
        size = _human_size(size_raw if isinstance(size_raw, int) else None)
        lines.append(f"{path}  {size}" if size else path)
    return "\n".join(lines)


def _collect_entries(
    root: Path,
    target: Path,
    max_depth: int,
    current_depth: int,
    entries: list[dict[str, object]],
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
        if not _is_included(root, child):
            continue

        entries.append(_entry_for(root, child))

        descend = child.is_dir() and current_depth < max_depth
        if descend and _collect_entries(
            root, child, max_depth, current_depth + 1, entries
        ):
            return True

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
        **kwargs: object,
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

        entries: list[dict[str, object]] = []
        truncated = _collect_entries(root, root, depth, 1, entries)

        count = len(entries)
        return ToolResult(
            success=True,
            data={
                "entries": entries,
                "count": count,
                "truncated": truncated,
            },
            text=render_text(
                entries=entries,
                count=count,
                truncated=truncated,
            ),
        )
