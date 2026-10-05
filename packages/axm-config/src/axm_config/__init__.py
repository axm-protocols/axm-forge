"""axm-config.

Non-sensitive runtime config under ~/.axm (env>file>default)
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_config.home import axm_home, axm_home_path, resolve_safe
    from axm_config.isolation import (
        ProfileIsolation,
        is_isolated,
        profile_isolation,
    )
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
        service_port,
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
        profile_root_for,
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
        get_file_namespace,
        list_execution_policies,
        load,
        set_,
        set_execution_policy,
        validate_segment,
    )
    from axm_config.store import NamespaceStore
    from axm_config.tools import ProfileIsolationTool

# Public names are resolved lazily (PEP 562): the pytest11 plugin
# ``axm_config.pytest_plugin`` is imported by every pytest session before
# coverage starts, so the package root must not import its submodules eagerly.
_EXPORTS: dict[str, str] = {
    **dict.fromkeys(("axm_home", "axm_home_path", "resolve_safe"), "home"),
    **dict.fromkeys(
        ("ProfileIsolation", "is_isolated", "profile_isolation"), "isolation"
    ),
    **dict.fromkeys(
        (
            "PATHS_NAMESPACE",
            "get_bool",
            "get_int",
            "get_path",
            "get_str",
            "inference_base_url",
            "inference_model",
            "inference_origin",
            "protocols_dir",
            "quality_dir",
            "service_port",
            "sessions_root",
            "tickets_db",
            "warden_autostart",
            "warden_binary_path",
            "warden_log_path",
            "warden_max_concurrent",
            "warden_mode",
            "warden_park_threshold",
            "warden_socket",
        ),
        "paths",
    ),
    **dict.fromkeys(
        (
            "current_profile",
            "profile_config_path",
            "profile_env",
            "profile_root",
            "profile_root_for",
        ),
        "profile",
    ),
    **dict.fromkeys(
        (
            "ConfigError",
            "ExecutionPolicyOverride",
            "UnsafeHomeError",
            "delete",
            "delete_execution_policy",
            "get",
            "get_execution_policy",
            "get_file",
            "get_file_namespace",
            "list_execution_policies",
            "load",
            "set_",
            "set_execution_policy",
            "validate_segment",
        ),
        "resolver",
    ),
    "NamespaceStore": "store",
    "ProfileIsolationTool": "tools",
}


def __getattr__(name: str) -> object:
    """Resolve a public name from its submodule on first access."""
    module = _EXPORTS.get(name)
    if module is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(importlib.import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the lazily exported public names."""
    return sorted({*globals(), *__all__})


__all__ = [
    "PATHS_NAMESPACE",
    "ConfigError",
    "ExecutionPolicyOverride",
    "NamespaceStore",
    "ProfileIsolation",
    "ProfileIsolationTool",
    "UnsafeHomeError",
    "axm_home",
    "axm_home_path",
    "current_profile",
    "delete",
    "delete_execution_policy",
    "get",
    "get_bool",
    "get_execution_policy",
    "get_file",
    "get_file_namespace",
    "get_int",
    "get_path",
    "get_str",
    "inference_base_url",
    "inference_model",
    "inference_origin",
    "is_isolated",
    "list_execution_policies",
    "load",
    "profile_config_path",
    "profile_env",
    "profile_isolation",
    "profile_root",
    "profile_root_for",
    "protocols_dir",
    "quality_dir",
    "resolve_safe",
    "service_port",
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
