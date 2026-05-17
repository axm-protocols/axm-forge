"""Working directory resolution helpers for git hooks."""

from __future__ import annotations

from pathlib import Path
from typing import cast

__all__ = ["resolve_working_dir"]


def resolve_working_dir(
    params: dict[str, object],
    context: dict[str, object],
    *,
    param_key: str = "working_dir",
) -> Path:
    """Resolve the working directory from params and context.

    Handles the case where ``worktree_path`` in context is a dict
    (as stored by ``WorktreeAddHook`` via ``inject_result``).

    Args:
        params: Hook keyword parameters.
        context: Session context dictionary.
        param_key: Parameter key to check first (default ``"working_dir"``).

    Returns:
        Resolved working directory as a Path.
    """
    raw: object = params.get(
        param_key,
        context.get("worktree_path", context.get("working_dir", ".")),
    )
    if isinstance(raw, dict):
        nested = cast("dict[str, object]", raw)
        raw = nested.get("worktree_path", nested.get("path", "."))
    return Path(cast("str | Path", raw))
