"""Git hook actions for AXM lifecycle hooks.

Provides MergeSquashHook,
PushHook, CreatePRHook, and AwaitMergeHook,
auto-discovered by ``HookRegistry`` via the ``axm.hooks``
entry-point group.
"""

from axm_git.hooks.await_merge import AwaitMergeHook
from axm_git.hooks.create_pr import CreatePRHook
from axm_git.hooks.merge_squash import MergeSquashHook
from axm_git.hooks.push import PushHook

__all__ = [
    "AwaitMergeHook",
    "CreatePRHook",
    "MergeSquashHook",
    "PushHook",
]
