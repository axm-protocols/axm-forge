"""Git hook actions for AXM lifecycle hooks.

Provides BranchDeleteHook, CreateBranchHook, CommitPhaseHook,
MergeSquashHook, PreflightHook, WorktreeAddHook, WorktreeRemoveHook,
PushHook, CreatePRHook, and AwaitMergeHook,
auto-discovered by ``HookRegistry`` via the ``axm.hooks``
entry-point group.
"""

from axm_git.hooks.await_merge import AwaitMergeHook
from axm_git.hooks.branch_delete import BranchDeleteHook
from axm_git.hooks.commit_phase import CommitPhaseHook
from axm_git.hooks.create_branch import CreateBranchHook
from axm_git.hooks.create_pr import CreatePRHook
from axm_git.hooks.merge_squash import MergeSquashHook
from axm_git.hooks.preflight import PreflightHook
from axm_git.hooks.push import PushHook
from axm_git.hooks.worktree_add import WorktreeAddHook
from axm_git.hooks.worktree_remove import WorktreeRemoveHook

__all__ = [
    "AwaitMergeHook",
    "BranchDeleteHook",
    "CommitPhaseHook",
    "CreateBranchHook",
    "CreatePRHook",
    "MergeSquashHook",
    "PreflightHook",
    "PushHook",
    "WorktreeAddHook",
    "WorktreeRemoveHook",
]
