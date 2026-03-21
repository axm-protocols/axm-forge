"""Pull hook action.

Pulls a remote branch (default ``origin main``) into the local repository.
Used after worktree merge to keep the main branch up to date.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import run_git
from axm_git.hooks._resolve import _resolve_working_dir

__all__ = ["PullHook"]


@dataclass
class PullHook:
    """Pull ``origin main`` into the local repository.

    Reads optional ``branch`` and ``remote`` from *params*.
    Skips gracefully when the working directory is not a git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``enabled`` (default ``True``),
                ``branch`` (default ``"main"``), ``remote`` (default ``"origin"``).

        Returns:
            HookResult with ``pulled`` and ``branch`` in metadata.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        working_dir = _resolve_working_dir(params, context)

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        remote = params.get("remote", "origin")
        branch = params.get("branch", "main")

        result = run_git(["pull", remote, branch], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git pull failed: {result.stderr.strip()}")

        return HookResult.ok(pulled=True, branch=branch)
