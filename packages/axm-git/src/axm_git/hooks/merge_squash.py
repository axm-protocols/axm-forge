"""Merge-squash hook action.

Merges a session branch back to the target branch with ``--squash``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from axm.hooks.base import HookResult

from axm_git.core.identity import resolve_identity
from axm_git.core.runner import find_git_root, run_git
from axm_git.hooks._resolve import resolve_working_dir
from axm_git.hooks.commit_phase import build_commit_cmd

__all__ = ["MergeSquashHook"]


@dataclass
class MergeSquashHook:
    """Merge session branch back to main with squash.

    Branch name priority: ``branch`` param > ``context["branch"]``
    > ``{prefix}/{session_id}`` fallback.

    Commit message priority: ``message`` param >
    ``[AXM] {protocol_name}: {session_id}`` fallback.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary (must contain
                ``session_id`` and ``protocol_name``).
            **params: Optional ``branch``, ``message``, ``prefix``,
                and ``target_branch``.

        Returns:
            HookResult with ``merged``, ``into``, and ``message`` in metadata.
        """
        working_dir = resolve_working_dir(params, context)
        session_id = cast("str", context["session_id"])
        protocol_name = cast("str", context["protocol_name"])

        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        git_root = find_git_root(working_dir)
        if git_root is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        branch = self._resolve_branch(params, context, session_id)
        target = cast("str", params.get("target_branch", "main"))

        # Checkout target branch
        result = run_git(["checkout", target], git_root)
        if result.returncode != 0:
            return HookResult.fail(f"checkout {target} failed: {result.stderr}")

        # Merge with squash
        result = run_git(["merge", "--squash", branch], git_root)
        if result.returncode != 0:
            return HookResult.fail(f"merge --squash failed: {result.stderr}")

        # Commit — route through the shared command builder and resolve
        # the author identity exactly like ``commit_from_outputs`` does,
        # so squash merges honour the identity-profile system.
        msg = cast(
            "str",
            params.get("message") or f"[AXM] {protocol_name}: {session_id}",
        )
        identity = resolve_identity(git_root)
        author = f"{identity.name} <{identity.email}>" if identity else None
        commit_cmd = build_commit_cmd(msg, None, skip_hooks=False, author=author)
        result = run_git(commit_cmd, git_root)
        if result.returncode != 0:
            return HookResult.fail(f"commit failed: {result.stderr}")

        return HookResult.ok(merged=branch, into=target, message=msg)

    @staticmethod
    def _resolve_branch(
        params: dict[str, object],
        context: dict[str, object],
        session_id: str,
    ) -> str:
        """Resolve branch name from params, context, then fallback."""
        if branch := params.get("branch"):
            return str(branch)
        if branch := context.get("branch"):
            return str(branch)
        prefix = params.get("prefix", "axm")
        return f"{prefix}/{session_id}"
