"""Canonical uv-workspace resolution.

Parses ``[tool.uv.workspace]`` from a root ``pyproject.toml``, resolves the
``members`` globs to directories, applies ``exclude`` and the
``require_pyproject`` rule, and returns sorted :class:`Member` records.

STDLIB only (``tomllib`` + ``pathlib``). Defensive parsing: an absent or
malformed pyproject never raises -- it yields ``None``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from axm_ingot.uv.models import Member, ResolvedWorkspace

__all__ = ["find_workspace_root", "resolve_workspace"]

_PYPROJECT = "pyproject.toml"


def _load_pyproject(directory: Path) -> dict[str, object] | None:
    """Parse ``directory/pyproject.toml`` defensively; ``None`` on any failure."""
    pyproject = directory / _PYPROJECT
    try:
        with pyproject.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def _get_workspace_config(data: dict[str, object]) -> dict[str, object] | None:
    """Return the ``[tool.uv.workspace]`` table, or ``None`` if absent."""
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    uv = tool.get("uv")
    if not isinstance(uv, dict):
        return None
    workspace = uv.get("workspace")
    if not isinstance(workspace, dict):
        return None
    return workspace


def _resolve_glob_dirs(root: Path, patterns: object) -> set[Path]:
    """Expand a list of glob patterns (relative to ``root``) to directories."""
    dirs: set[Path] = set()
    if not isinstance(patterns, list):
        return dirs
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        for match in root.glob(pattern):
            if match.is_dir():
                dirs.add(match.resolve())
    return dirs


def resolve_workspace(pyproject_dir: Path) -> ResolvedWorkspace | None:
    """Resolve the uv workspace rooted at ``pyproject_dir``.

    Parses ``[tool.uv.workspace].members``, resolves the globs to directories,
    subtracts the ``exclude`` globs, keeps only directories that contain a
    ``pyproject.toml`` (``require_pyproject``), and returns the members sorted
    by name. Returns ``None`` when ``pyproject_dir`` is not a uv workspace or
    its pyproject is missing/malformed.
    """
    root = pyproject_dir.resolve()
    data = _load_pyproject(root)
    if data is None:
        return None
    workspace = _get_workspace_config(data)
    if workspace is None:
        return None

    included = _resolve_glob_dirs(root, workspace.get("members"))
    excluded = _resolve_glob_dirs(root, workspace.get("exclude"))
    members = tuple(
        sorted(
            (
                Member(name=directory.name, path=directory)
                for directory in included - excluded
                if (directory / _PYPROJECT).is_file()
            ),
            key=lambda member: member.name,
        )
    )
    return ResolvedWorkspace(root=root, members=members)


def find_workspace_root(path: Path) -> Path | None:
    """Walk parents from ``path`` to the first uv-workspace root.

    Returns the directory of the first ancestor (``path`` included) whose
    ``pyproject.toml`` carries a ``[tool.uv.workspace]`` section, else ``None``.
    """
    current = path.resolve()
    for directory in (current, *current.parents):
        data = _load_pyproject(directory)
        if data is not None and _get_workspace_config(data) is not None:
            return directory
    return None
