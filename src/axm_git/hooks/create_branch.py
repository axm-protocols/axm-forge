"""Create-branch hook action.

Creates a session branch ``{prefix}/{session_id}`` in the working directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_engine.services.hooks.base import HookResult

from axm_git.core.runner import run_git

__all__ = ["CreateBranchHook"]


@dataclass
class CreateBranchHook:
    """Create a session branch: ``{prefix}/{session_id}``.

    Reads ``session_id`` from *context* and an optional ``prefix``
    from *params* (default ``"axm"``).  Skips gracefully when
    the working directory is not a git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain ``session_id``).
            **params: Optional ``prefix`` (default ``"axm"``).

        Returns:
            HookResult with ``branch`` in metadata on success.
        """
        working_dir = Path(context.get("working_dir", "."))
        session_id: str = context["session_id"]

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        prefix = params.get("prefix", "axm")
        branch = f"{prefix}/{session_id}"

        result = run_git(["checkout", "-b", branch], working_dir)
        if result.returncode != 0:
            return HookResult.fail(f"git checkout -b failed: {result.stderr}")

        return HookResult.ok(branch=branch)
