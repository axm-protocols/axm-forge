"""Git hook actions for AXM lifecycle hooks.

Provides CreateBranchHook, CommitPhaseHook, MergeSquashHook,
PreflightHook, WorktreeAddHook, and WorktreeRemoveHook,
auto-discovered by ``HookRegistry`` via the ``axm.hooks``
entry-point group.
"""

from axm_git.hooks.commit_phase import CommitPhaseHook
from axm_git.hooks.create_branch import CreateBranchHook
from axm_git.hooks.merge_squash import MergeSquashHook
from axm_git.hooks.preflight import PreflightHook
from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook

__all__ = [
    "CommitPhaseHook",
    "CreateBranchHook",
    "MergeSquashHook",
    "PreflightHook",
    "WorktreeAddHook",
    "WorktreeRemoveHook",
]
