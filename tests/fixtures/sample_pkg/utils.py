"""Utilities submodule."""

from pathlib import Path

from . import _InternalClass as _IC  # noqa: F401


def resolve_path(p: str) -> Path:
    """Resolve a string to an absolute Path.

    Args:
        p: String path to resolve.

    Returns:
        Resolved absolute Path.
    """
    return Path(p).resolve()


def find_files(root: Path, pattern: str = "*.py") -> list[Path]:
    """Find files matching a glob pattern.

    Args:
        root: Root directory to search.
        pattern: Glob pattern.

    Returns:
        List of matching paths.
    """
    return list(root.rglob(pattern))
