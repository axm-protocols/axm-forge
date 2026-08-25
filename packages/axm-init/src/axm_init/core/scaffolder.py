"""Shared scaffolding seam.

Single source of truth for the pieces that both the CLI (:mod:`axm_init.cli`)
and the MCP tool (:mod:`axm_init.tools.scaffold`) need when scaffolding a
workspace *member*: the copier template-variable build, workspace-root
resolution, and workspace-name read. Neither interface layer keeps a private
copy of this logic.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

__all__ = [
    "build_member_data",
    "next_experiment_index",
    "read_workspace_name",
    "resolve_workspace_root",
]

_DEFAULT_MEMBER_DESCRIPTION = "A workspace member package"


def build_member_data(
    member_name: str,
    workspace_name: str,
    scaffold_data: Mapping[str, str],
    *,
    license_holder: str | None = None,
) -> dict[str, str]:
    """Build copier template variables for a workspace member scaffold.

    Args:
        member_name: Name of the new member package.
        workspace_name: Parent workspace name (used for URLs).
        scaffold_data: Caller identity fields — ``org``, ``author_name``,
            ``author_email``, ``license`` and optionally ``description``.
        license_holder: Explicit LICENSE holder; falls back to ``org``.

    Returns:
        The template-variable dict passed verbatim to copier. Identical inputs
        yield a byte-identical dict whatever the calling interface.
    """
    org = scaffold_data["org"]
    return {
        "member_name": member_name,
        "workspace_name": workspace_name,
        "description": scaffold_data.get("description") or _DEFAULT_MEMBER_DESCRIPTION,
        "org": org,
        "license": scaffold_data["license"],
        "license_holder": license_holder or org,
        "author_name": scaffold_data["author_name"],
        "author_email": scaffold_data["author_email"],
    }


def resolve_workspace_root(target_path: Path) -> Path | None:
    """Resolve the workspace root for *target_path*, or ``None``.

    Returns *target_path* itself when it is a workspace root, the parent
    workspace root when *target_path* is a member, and ``None`` otherwise.
    """
    from axm_init.checks._workspace import (
        ProjectContext,
        detect_context,
        find_workspace_root,
    )

    context = detect_context(target_path)
    if context == ProjectContext.WORKSPACE:
        return target_path
    if context == ProjectContext.MEMBER:
        return find_workspace_root(target_path)
    return None


def read_workspace_name(workspace_root: Path) -> str:
    """Read the workspace name from ``pyproject.toml`` or fall back to dir name."""
    root_pyproject = workspace_root / "pyproject.toml"
    if root_pyproject.is_file():
        with open(root_pyproject, "rb") as f:
            root_data = tomllib.load(f)
        return str(root_data.get("project", {}).get("name", workspace_root.name))
    return workspace_root.name


def next_experiment_index(experiments_dir: Path) -> int:
    """Return the next free experiment index inside *experiments_dir*.

    The index belongs to the scaffolding layer, never to the copier template:
    an experiment directory is named ``{index:02d}-{slug}``, so the next free
    index is one past the highest index already present. A missing or empty
    ``experiments/`` directory yields ``1``.

    Args:
        experiments_dir: The paper's ``experiments/`` directory.

    Returns:
        The next free one-based index.
    """
    if not experiments_dir.is_dir():
        return 1
    highest = 0
    for entry in experiments_dir.iterdir():
        if not entry.is_dir():
            continue
        head = entry.name.split("-", 1)[0]
        if head.isdigit():
            highest = max(highest, int(head))
    return highest + 1
