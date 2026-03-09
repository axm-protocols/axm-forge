"""Git hook actions for AXM lifecycle hooks.

Provides CreateBranchHook, CommitPhaseHook, and MergeSquashHook,
auto-discovered by ``HookRegistry`` via the ``axm.hooks`` entry-point group.
"""

from axm_git.hooks.commit_phase import CommitPhaseHook
from axm_git.hooks.create_branch import CreateBranchHook
from axm_git.hooks.merge_squash import MergeSquashHook

__all__ = ["CommitPhaseHook", "CreateBranchHook", "MergeSquashHook"]
