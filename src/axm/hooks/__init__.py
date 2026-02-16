"""Hook base types for AXM lifecycle hooks.

Provides :class:`HookResult` and :class:`HookAction`, the shared
contracts used by all hook implementations across the ecosystem.
"""

from axm.hooks.base import HookAction, HookResult

__all__ = ["HookAction", "HookResult"]
