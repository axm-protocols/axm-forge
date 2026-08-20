"""axm-config.

Non-sensitive runtime config under ~/.axm (env>file>default)
"""

from __future__ import annotations

from axm_config.home import axm_home, resolve_safe
from axm_config.paths import (
    PATHS_NAMESPACE,
    get_bool,
    get_int,
    get_path,
    get_str,
    protocols_dir,
    quality_dir,
    sessions_root,
    warden_socket,
)
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
    "PATHS_NAMESPACE",
    "ConfigError",
    "ExecutionPolicyOverride",
    "NamespaceStore",
    "UnsafeHomeError",
    "axm_home",
    "delete",
    "delete_execution_policy",
    "get",
    "get_bool",
    "get_execution_policy",
    "get_int",
    "get_path",
    "get_str",
    "list_execution_policies",
    "load",
    "protocols_dir",
    "quality_dir",
    "resolve_safe",
    "sessions_root",
    "set_",
    "set_execution_policy",
    "validate_segment",
    "warden_socket",
]
