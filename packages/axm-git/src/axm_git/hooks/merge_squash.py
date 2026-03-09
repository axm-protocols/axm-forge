"""Merge-squash hook action.

Merges a session branch back to the target branch with ``--squash``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import run_git

__all__ = ["MergeSquashHook"]


@dataclass
class MergeSquashHook:
    """Merge session branch back to main with squash.

    Reads ``session_id`` and ``protocol_name`` from *context*.
    Optional ``prefix`` (default ``"axm"``) and ``target_branch``
    (default ``"main"``) can be set via *params*.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain
                ``session_id`` and ``protocol_name``).
            **params: Optional ``prefix`` and ``target_branch``.

        Returns:
            HookResult with ``merged``, ``into``, and ``message`` in metadata.
        """
        working_dir = Path(context.get("working_dir", "."))
        session_id: str = context["session_id"]
        protocol_name: str = context["protocol_name"]

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        prefix = params.get("prefix", "axm")
        branch = f"{prefix}/{session_id}"
        target = params.get("target_branch", "main")

        # Checkout target branch
        result = run_git(["checkout", target], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"checkout {target} failed: {result.stderr}")

        # Merge with squash
        result = run_git(["merge", "--squash", branch], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"merge --squash failed: {result.stderr}")

        # Commit
        msg = f"[AXM] {protocol_name}: {session_id}"
        result = run_git(["commit", "-m", msg], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"commit failed: {result.stderr}")

        return HookResult.ok(merged=branch, into=target, message=msg)
