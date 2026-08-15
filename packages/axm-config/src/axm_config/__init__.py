"""axm-config.

Non-sensitive runtime config under ~/.axm (env>file>default)
"""

from __future__ import annotations

from axm_config.home import axm_home, resolve_safe
from axm_config.resolver import (
    ConfigError,
    ExecutionPolicyOverride,
    UnsafeHomeError,
    delete,
    delete_execution_policy,
    get,
    get_execution_policy,
    list_execution_policies,
    load,
    set_,
    set_execution_policy,
    validate_segment,
)
from axm_config.store import NamespaceStore

__all__ = [
    "ConfigError",
    "ExecutionPolicyOverride",
    "NamespaceStore",
    "UnsafeHomeError",
    "axm_home",
    "delete",
    "delete_execution_policy",
    "get",
    "get_execution_policy",
    "list_execution_policies",
    "load",
    "resolve_safe",
    "set_",
    "set_execution_policy",
    "validate_segment",
]
