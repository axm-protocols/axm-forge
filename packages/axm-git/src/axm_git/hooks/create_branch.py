"""Create-branch hook action.

Creates a session branch in the working directory.  Branch name is resolved
with priority: ``branch`` param > ticket params > ``{prefix}/{session_id}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.branch_naming import branch_name_from_ticket
from axm_git.core.runner import run_git
from axm_git.hooks._resolve import _resolve_working_dir

__all__ = ["CreateBranchHook"]


@dataclass
class CreateBranchHook:
    """Create a session branch.

    Branch name priority:

    1. ``branch`` param (direct override)
    2. ``ticket_id`` + ``ticket_title`` params → ``branch_name_from_ticket()``
    3. ``{prefix}/{session_id}`` (legacy fallback)

    Skips gracefully when the working directory is not a git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``session_id``).
            **params: Optional ``branch``, ``ticket_id``, ``ticket_title``,
                ``ticket_labels``, ``prefix`` (default ``"axm"``).

        Returns:
            HookResult with ``branch`` in metadata on success.
        """
        working_dir = _resolve_working_dir(params, context)
        session_id: str = context["session_id"]

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        branch = self._resolve_branch(params, session_id)

        result = run_git(["checkout", "-b", branch], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git checkout -b failed: {result.stderr}")

        return HookResult.ok(branch=branch)

    @staticmethod
    def _resolve_branch(params: dict[str, Any], session_id: str) -> str:
        """Resolve branch name from params with fallback to session_id."""
        if branch := params.get("branch"):
            return str(branch)

        ticket_id = params.get("ticket_id")
        ticket_title = params.get("ticket_title")
        if ticket_id and ticket_title:
            labels = params.get("ticket_labels", [])
            return branch_name_from_ticket(ticket_id, ticket_title, labels)

        prefix = params.get("prefix", "axm")
        return f"{prefix}/{session_id}"
