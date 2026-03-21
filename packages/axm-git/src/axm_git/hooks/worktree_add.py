"""Worktree-add hook action.

Creates a git worktree at ``/tmp/axm-worktrees/<ticket_id>/`` with a branch
derived from ticket metadata via ``branch_name_from_ticket()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.branch_naming import branch_name_from_ticket
from axm_git.core.runner import find_git_root, run_git

__all__ = ["WorktreeAddHook"]


@dataclass
class WorktreeAddHook:
    """Create a worktree + branch for a ticket.

    Reads ``ticket_id``, ``ticket_title``, ``ticket_labels``, and
    ``repo_path`` from *context*.  The worktree is placed under
    ``/tmp/axm-worktrees/<ticket_id>/``.

    Skips gracefully when the working directory is not a git repository
    or the worktree already exists.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context (must contain ``repo_path``,
                ``ticket_id``, ``ticket_title``, ``ticket_labels``).
            **params: Optional ``enabled`` (default ``True``).

        Returns:
            HookResult with ``worktree_path`` and ``branch`` in metadata.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        repo_path = Path(context.get("repo_path", "."))

        if find_git_root(repo_path) is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        ticket_id: str = context["ticket_id"]
        title: str = context["ticket_title"]
        labels: list[str] = context.get("ticket_labels", [])

        branch = branch_name_from_ticket(ticket_id, title, labels)
        worktree_path = Path("/tmp/axm-worktrees") / ticket_id  # noqa: S108
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        if worktree_path.exists():
            return HookResult.ok(
                skipped=True,
                reason=f"worktree already exists: {worktree_path}",
            )

        result = run_git(
            ["worktree", "add", "-b", branch, str(worktree_path), "main"],
            repo_path,
        )
        if result.returncode != 0:
            return HookResult.fail(f"git worktree add failed: {result.stderr}")

        return HookResult.ok(
            worktree_path=str(worktree_path),
            branch=branch,
        )
