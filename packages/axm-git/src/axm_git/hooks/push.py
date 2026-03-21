"""Push hook action.

Pushes the current branch to ``origin`` with upstream tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import run_git
from axm_git.hooks._resolve import _resolve_working_dir

__all__ = ["PushHook"]


@dataclass
class PushHook:
    """Push the current branch to ``origin -u``.

    Reads ``branch`` from *context* (or detects it from HEAD).
    Skips gracefully when the working directory is not a git repository.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``enabled`` (default ``True``).

        Returns:
            HookResult with ``pushed`` and ``branch`` in metadata.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        working_dir = _resolve_working_dir(params, context)

        if not (working_dir / ".git").exists():
            return HookResult.ok(skipped=True, reason="not a git repo")

        branch = context.get("branch")
        if not branch:
            head = run_git(["rev-parse", "--abbrev-ref", "HEAD"], working_dir)
            if head.returncode != 0:
                return HookResult.fail(f"failed to detect branch: {head.stderr}")
            branch = head.stdout.strip()

        result = run_git(["push", "-u", "origin", branch], working_dir)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Everything up-to-date" in (result.stderr + result.stdout):
                return HookResult.ok(pushed=True, branch=branch)
            return HookResult.fail(f"git push failed: {stderr}")

        return HookResult.ok(pushed=True, branch=branch)
