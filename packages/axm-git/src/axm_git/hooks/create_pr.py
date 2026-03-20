"""Create-PR hook action.

Creates a GitHub pull request with conventional commit title and auto-merge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_git.core.runner import gh_available, run_gh

__all__ = ["CreatePRHook"]


def _format_pr_title(commit_spec: dict[str, Any], ticket_id: str) -> str:
    """Format PR title from commit spec message.

    If the message already contains ``[AXM-...]``, use it as-is.
    Otherwise append ``[{ticket_id}]``.
    """
    message = str(commit_spec.get("message", ""))
    if ticket_id and f"[{ticket_id}]" not in message:
        return f"{message} [{ticket_id}]"
    return message


@dataclass
class CreatePRHook:
    """Create a GitHub PR with auto-merge squash.

    Reads ``branch``, ``commit_spec``, and ``ticket_id`` from *context*.
    Runs ``gh pr create`` followed by ``gh pr merge --auto --squash``.
    Skips gracefully when ``gh`` is not installed.
    """

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``enabled`` (default ``True``),
                ``base`` (default ``"main"``).

        Returns:
            HookResult with ``pr_url`` and ``pr_number`` in metadata.
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

        commit_spec: dict[str, Any] = context.get("commit_spec", {})
        ticket_id: str = context.get("ticket_id", "")
        base = params.get("base", "main")

        title = _format_pr_title(commit_spec, ticket_id)
        body = commit_spec.get("body", "")

        # Create the PR
        create_args = [
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--base",
            base,
        ]
        result = run_gh(create_args, working_dir)

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "already exists" in stderr:
                return _recover_existing_pr(working_dir)
            return HookResult.fail(f"gh pr create failed: {stderr}")

        pr_url = result.stdout.strip()

        # Extract PR number from URL
        pr_number = pr_url.rstrip("/").rsplit("/", maxsplit=1)[-1]

        # Enable auto-merge
        merge_result = run_gh(
            ["pr", "merge", pr_number, "--auto", "--squash"],
            working_dir,
        )
        if merge_result.returncode != 0:
            # Non-fatal: PR created but auto-merge not enabled
            return HookResult.ok(
                pr_url=pr_url,
                pr_number=pr_number,
                auto_merge=False,
                auto_merge_error=merge_result.stderr.strip(),
            )

        return HookResult.ok(
            pr_url=pr_url,
            pr_number=pr_number,
            auto_merge=True,
        )


def _recover_existing_pr(working_dir: Path) -> HookResult:
    """Extract existing PR URL when creation fails with 'already exists'."""
    view = run_gh(["pr", "view", "--json", "url,number"], working_dir)
    if view.returncode != 0:
        return HookResult.fail(
            f"PR already exists but could not retrieve it: {view.stderr}"
        )
    data = json.loads(view.stdout)
    return HookResult.ok(
        pr_url=data["url"],
        pr_number=str(data["number"]),
        already_existed=True,
    )
