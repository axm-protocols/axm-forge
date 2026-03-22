"""Delete-branch hook action.

Deletes a branch by name via ``git branch -D``.  Branch name is resolved
with priority: ``branch`` param > ``branch`` context key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import find_git_root, run_git
from axm_git.hooks._resolve import _resolve_working_dir

__all__ = ["BranchDeleteHook"]


@dataclass
class BranchDeleteHook:
    """Delete a branch by name.

    Branch name priority:

    1. ``branch`` param (direct override)
    2. ``branch`` context key

    Skips gracefully when disabled or when the working directory is not
    a git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``branch``, ``enabled``, ``working_dir``.

        Returns:
            HookResult with ``branch`` and ``deleted`` in metadata on success.
        """
        working_dir = _resolve_working_dir(params, context)

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        git_root = find_git_root(working_dir)
        if git_root is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        branch = params.get("branch") or context.get("branch")
        if not branch:
            return HookResult.fail("no branch specified in params or context")

        result = run_git(["branch", "-D", branch], git_root)
        if result.returncode != 0:
            return HookResult.fail(f"git branch -D failed: {result.stderr}")

        return HookResult.ok(branch=branch, deleted=True)
