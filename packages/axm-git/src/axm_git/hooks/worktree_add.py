"""Worktree-add hook action.

Creates a git worktree under a configurable root — ``<root>/<ticket_id>/`` —
with a branch derived from ticket metadata via ``branch_name_from_ticket()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from axm.hooks.base import HookResult
from axm_config import NamespaceStore

from axm_git.core.branch_naming import branch_name_from_ticket
from axm_git.core.runner import find_git_root, run_git

__all__ = ["DEFAULT_WORKTREE_ROOT", "WorktreeAddHook", "resolve_worktree_root"]

#: Where worktrees land when nothing says otherwise — the historical location,
#: kept as the default so existing callers see no change.
DEFAULT_WORKTREE_ROOT = Path("/tmp/axm-worktrees")  # noqa: S108


def resolve_worktree_root(context: dict[str, object]) -> Path:
    """Resolve where worktrees are created: context > config > default.

    The root used to be the constant ``/tmp/axm-worktrees``, which makes two
    concurrent executions collide: the second finds the first's directory and
    fails with "a branch named … already exists". That is not hypothetical — the
    warden runs with ``--max-concurrent`` above 1, so two tickets touching the
    same repo hit it. It surfaced first under a parallel test run, where four
    worktree tests broke at once.

    A destination path is a configuration decision, not a code constant, so it
    follows the house resolution order: an explicit ``worktree_root`` in the
    context wins (a caller that knows where it wants its worktree), then the
    ``git.worktree_root`` config key, then :data:`DEFAULT_WORKTREE_ROOT`.

    A config read that fails for any reason falls through to the default rather
    than raising: this hook is best-effort and must not turn a missing or
    malformed config into a failed ticket.
    """
    explicit = context.get("worktree_root")
    if explicit:
        return Path(str(explicit))
    try:
        configured = NamespaceStore().read("git").get("worktree_root")
    except Exception:  # noqa: BLE001 - config is advisory, never fatal here
        configured = None
    return Path(str(configured)) if configured else DEFAULT_WORKTREE_ROOT


@dataclass
class WorktreeAddHook:
    """Create a worktree + branch for a ticket.

    Reads ``ticket_id``, ``ticket_title``, ``ticket_labels``, and
    ``repo_path`` from *context*. The worktree is placed under
    ``<root>/<ticket_id>/``, the root resolved by
    :func:`resolve_worktree_root` (context > config > default).

    Skips gracefully when the working directory is not a git repository
    or the worktree already exists.
    """

    def execute(self, context: dict[str, object], **params: object) -> HookResult:
        """Execute the hook action.

        Args:
            context: Session context dictionary.
            **params: Optional ``repo_path``, ``ticket_id``,
                ``ticket_title``, ``ticket_labels``, ``enabled``
                (default ``True``).  Params take precedence over context.

        Returns:
            HookResult with ``worktree_path`` and ``branch`` in metadata.
        """
        if not params.get("enabled", True):
            return HookResult.ok(skipped=True, reason="git disabled")

        repo_path = Path(
            cast(
                "str | Path",
                params.get("repo_path", context.get("repo_path", ".")),
            )
        )

        if find_git_root(repo_path) is None:
            return HookResult.ok(skipped=True, reason="not a git repo")

        ticket_id = cast(
            "str",
            params["ticket_id"] if "ticket_id" in params else context["ticket_id"],
        )
        title = cast(
            "str",
            params["ticket_title"]
            if "ticket_title" in params
            else context["ticket_title"],
        )
        labels = cast(
            "list[str]",
            params.get("ticket_labels", context.get("ticket_labels", [])),
        )

        branch = branch_name_from_ticket(ticket_id, title, labels)
        worktree_path = resolve_worktree_root(dict(context)) / ticket_id
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
