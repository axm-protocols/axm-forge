"""Workspace context detection for UV workspaces.

Detects whether a project path is a standalone package, a UV workspace
root, or a member of a UV workspace.  Used by the check engine to
filter checks by context.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

__all__ = [
    "ProjectContext",
    "detect_context",
    "find_workspace_root",
    "get_workspace_members",
]


class ProjectContext(StrEnum):
    """Project context within a UV workspace layout."""

    STANDALONE = "standalone"
    WORKSPACE = "workspace"
    MEMBER = "member"


def _load_pyproject(path: Path) -> dict[str, Any] | None:
    """Load pyproject.toml at *path*, return ``None`` on failure."""
    toml_path = path / "pyproject.toml"
    if not toml_path.exists():
        return None
    try:
        with toml_path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        logger.debug("Failed to parse %s", toml_path, exc_info=True)
        return None


def _has_workspace_section(data: dict[str, Any]) -> bool:
    """Check if parsed TOML data contains ``[tool.uv.workspace]``."""
    return bool(data.get("tool", {}).get("uv", {}).get("workspace"))


def _get_workspace_config(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the ``[tool.uv.workspace]`` section."""
    result: dict[str, Any] = data.get("tool", {}).get("uv", {}).get("workspace", {})
    return result


def find_workspace_root(path: Path) -> Path | None:
    """Walk parent directories looking for a UV workspace root.

    A workspace root is a directory whose ``pyproject.toml`` contains a
    ``[tool.uv.workspace]`` section.

    Args:
        path: Starting directory (typically a member package).

    Returns:
        The workspace root ``Path``, or ``None`` if not found.
    """
    for parent in path.resolve().parents:
        data = _load_pyproject(parent)
        if data is not None and _has_workspace_section(data):
            return parent
    return None


def detect_context(path: Path) -> ProjectContext:
    """Detect whether *path* is a standalone package, workspace, or member.

    Detection logic:

    1. If *path*/pyproject.toml has ``[tool.uv.workspace]`` → ``WORKSPACE``
    2. If a parent directory is a workspace root → ``MEMBER``
    3. Otherwise → ``STANDALONE``

    Gracefully falls back to ``STANDALONE`` on missing or corrupt TOML.

    Args:
        path: Project root directory to inspect.

    Returns:
        The detected ``ProjectContext``.
    """
    data = _load_pyproject(path)

    # Case 1: this path IS a workspace root
    if data is not None and _has_workspace_section(data):
        return ProjectContext.WORKSPACE

    # Case 2: check if a parent is a workspace root
    root = find_workspace_root(path)
    if root is not None:
        return ProjectContext.MEMBER

    # Case 3: standalone (including missing/corrupt TOML)
    return ProjectContext.STANDALONE


def _resolve_glob_dirs(
    root: Path,
    globs: list[str],
    *,
    require_pyproject: bool = False,
) -> set[Path]:
    """Resolve glob patterns to directories under *root*.

    Args:
        root: Base directory for glob resolution.
        globs: List of glob patterns.
        require_pyproject: If ``True``, only include dirs with pyproject.toml.

    Returns:
        Set of matching directory paths.
    """
    dirs: set[Path] = set()
    for pattern in globs:
        for match in root.glob(pattern):
            if not match.is_dir():
                continue
            if require_pyproject and not (match / "pyproject.toml").exists():
                continue
            dirs.add(match)
    return dirs


def get_workspace_members(path: Path) -> list[str]:
    """Resolve workspace member package names from *path*.

    Reads the ``members`` globs from ``[tool.uv.workspace]`` in the
    pyproject.toml at *path*, resolves them via ``Path.glob()``, and
    filters out directories matching ``exclude`` globs.

    Each resolved directory must contain a ``pyproject.toml`` to be
    considered a valid member.

    Args:
        path: Workspace root directory.

    Returns:
        Sorted list of member directory names (relative to *path*).
    """
    data = _load_pyproject(path)
    if data is None:
        return []

    ws_config = _get_workspace_config(data)
    if not ws_config:
        return []

    resolved = path.resolve()
    member_dirs = _resolve_glob_dirs(
        resolved,
        ws_config.get("members", []),
        require_pyproject=True,
    )
    exclude_dirs = _resolve_glob_dirs(
        resolved,
        ws_config.get("exclude", []),
    )

    return sorted(m.name for m in member_dirs - exclude_dirs)
