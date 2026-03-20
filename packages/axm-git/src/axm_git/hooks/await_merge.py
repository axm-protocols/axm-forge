"""Await-merge hook action.

Polls a GitHub PR until it reaches the ``MERGED`` state.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import gh_available, run_gh

__all__ = ["AwaitMergeHook"]

_DEFAULT_TIMEOUT = 600  # 10 minutes
_DEFAULT_INTERVAL = 30  # seconds


@dataclass
class AwaitMergeHook:
    """Poll a PR until merged or timeout.

    Reads ``pr_number`` (or ``pr_url``) from *context* and polls
    ``gh pr view --json state`` every 30 seconds.  Times out after
    10 minutes by default.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain
                ``pr_number`` or ``pr_url``).
            **params: Optional ``enabled``, ``timeout`` (seconds),
                ``interval`` (seconds).

        Returns:
            HookResult with ``merged=True`` on success.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if not gh_available():
            return HookResult.ok(skipped=True, reason="gh not available")

        working_dir = Path(
            params.get(
                "working_dir",
                context.get("worktree_path", context.get("working_dir", ".")),
            )
        )

        pr_ref = context.get("pr_number") or context.get("pr_url")
        if not pr_ref:
            return HookResult.fail("no pr_number or pr_url in context")

        timeout = int(params.get("timeout", _DEFAULT_TIMEOUT))
        interval = int(params.get("interval", _DEFAULT_INTERVAL))

        elapsed = 0
        while elapsed < timeout:
            state = _poll_pr_state(str(pr_ref), working_dir)
            if state is None:
                return HookResult.fail(f"failed to query PR {pr_ref} state")
            if state == "MERGED":
                return HookResult.ok(merged=True, pr_ref=str(pr_ref))
            if state == "CLOSED":
                return HookResult.fail(f"PR {pr_ref} was closed without merging")

            time.sleep(interval)
            elapsed += interval

        return HookResult.fail(f"PR {pr_ref} not merged after {timeout}s timeout")


def _poll_pr_state(pr_ref: str, working_dir: Path) -> str | None:
    """Query the current state of a PR.

    Returns:
        State string (``"OPEN"``, ``"MERGED"``, ``"CLOSED"``)
        or ``None`` on error.
    """
    result = run_gh(
        ["pr", "view", pr_ref, "--json", "state"],
        working_dir,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)["state"]  # type: ignore[no-any-return]
    except (json.JSONDecodeError, KeyError):
        return None
