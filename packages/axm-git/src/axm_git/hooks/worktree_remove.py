"""Worktree-remove hook action.

Removes a git worktree previously created by ``WorktreeAddHook``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import find_git_root, run_git
from axm_git.hooks._resolve import _resolve_working_dir

__all__ = ["WorktreeRemoveHook"]


@dataclass
class WorktreeRemoveHook:
    """Remove a worktree after merge.

    Reads ``worktree_path`` and ``repo_path`` from *context*.
    Uses ``git worktree remove --force`` to handle dirty worktrees.
    Skips gracefully when the path doesn't exist or isn't a git repo.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context (must contain ``repo_path``
                and ``worktree_path``).
            **params: Optional ``enabled`` (default ``True``).

        Returns:
            HookResult on success.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        repo_path = Path(context.get("repo_path", "."))

        if find_git_root(repo_path) is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        worktree_path = _resolve_working_dir({}, context)

        if not worktree_path.exists():
            return HookResult.ok(
                skipped=True,
                reason=f"worktree path does not exist: {worktree_path}",
            )

        result = run_git(
            ["worktree", "remove", str(worktree_path), "--force"],
            repo_path,
        )
        if result.returncode != 0:
            return HookResult.fail(
                f"git worktree remove failed: {result.stderr}",
            )

        return HookResult.ok()
