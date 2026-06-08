"""Create-PR hook action.

Creates a GitHub pull request with conventional commit title and auto-merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from axm.hooks.base import HookResult

from axm_git.core.pr_recovery import recover_existing_pr
from axm_git.core.runner import gh_available, run_gh
from axm_git.hooks._resolve import resolve_working_dir

__all__ = ["CreatePRHook"]


def format_pr_title(commit_spec: dict[str, object], ticket_id: str) -> str:
    """Format PR title from commit spec message.

    If the message already contains ``[AXM-...]``, use it as-is.
    Otherwise append ``[{ticket_id}]``.
    """
    message = str(commit_spec.get("message", ""))
    if ticket_id and f"[{ticket_id}]" not in message:
        return f"{message} [{ticket_id}]"
    return message


def _handle_create_failure(stderr: str, working_dir: Path) -> HookResult:
    """Map a ``gh pr create`` failure to a :class:`HookResult`.

    On an 'already exists' error, recover the existing PR via the shared
    helper; otherwise surface the original failure.
    """
    if "already exists" in stderr:
        recovery = recover_existing_pr(working_dir)
        if not recovery.ok:
            return HookResult.fail(recovery.error or "PR recovery failed")
        return HookResult.ok(
            pr_url=recovery.url,
            pr_number=recovery.number,
            already_existed=recovery.already_existed,
        )
    return HookResult.fail(f"gh pr create failed: {stderr}")


@dataclass
class CreatePRHook:
    """Create a GitHub PR with auto-merge squash.

    Reads ``branch``, ``commit_spec``, and ``ticket_id`` from *context*.
    Runs ``gh pr create`` followed by ``gh pr merge --auto --squash``.
    Skips gracefully when ``gh`` is not installed.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``enabled`` (default ``True``),
                ``base`` (default ``"main"``), ``commit_spec``,
                ``ticket_id``.  Params take precedence over context.

        Returns:
            HookResult with ``pr_url`` and ``pr_number`` in metadata.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        if not gh_available():
            return HookResult.ok(skipped=True, reason="gh not available")

        working_dir = resolve_working_dir(params, context)

        commit_spec = cast(
            "dict[str, object]",
            params.get("commit_spec", context.get("commit_spec", {})),
        )
        ticket_id = cast("str", params.get("ticket_id", context.get("ticket_id", "")))
        base = cast("str", params.get("base", "main"))

        title = format_pr_title(commit_spec, ticket_id)
        body = cast("str", commit_spec.get("body", ""))

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
            return _handle_create_failure(result.stderr.strip(), working_dir)

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
