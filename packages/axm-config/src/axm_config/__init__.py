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
    inference_base_url,
    inference_model,
    inference_origin,
    protocols_dir,
    quality_dir,
    sessions_root,
    tickets_db,
    warden_autostart,
    warden_binary_path,
    warden_log_path,
    warden_max_concurrent,
    warden_mode,
    warden_park_threshold,
    warden_socket,
)
from axm_config.profile import (
    current_profile,
    profile_config_path,
    profile_env,
    profile_root,
)
from axm_config.resolver import (
    ConfigError,
    ExecutionPolicyOverride,
    UnsafeHomeError,
    delete,
    delete_execution_policy,
    get,
    get_execution_policy,
    get_file,
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
    "current_profile",
    "delete",
    "delete_execution_policy",
    "get",
    "get_bool",
    "get_execution_policy",
    "get_file",
    "get_int",
    "get_path",
    "get_str",
    "inference_base_url",
    "inference_model",
    "inference_origin",
    "list_execution_policies",
    "load",
    "profile_config_path",
    "profile_env",
    "profile_root",
    "protocols_dir",
    "quality_dir",
    "resolve_safe",
    "sessions_root",
    "set_",
    "set_execution_policy",
    "tickets_db",
    "validate_segment",
    "warden_autostart",
    "warden_binary_path",
    "warden_log_path",
    "warden_max_concurrent",
    "warden_mode",
    "warden_park_threshold",
    "warden_socket",
]
