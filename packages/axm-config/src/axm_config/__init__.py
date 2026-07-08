"""axm-config.

Non-sensitive runtime config under ~/.axm (env>file>default)
"""

from __future__ import annotations

from axm_config.home import axm_home, resolve_safe
from axm_config.resolver import (
    ConfigError,
    UnsafeHomeError,
    delete,
    get,
    load,
    set_,
    validate_segment,
)
from axm_config.store import NamespaceStore

__all__ = [
    "ConfigError",
    "NamespaceStore",
    "UnsafeHomeError",
    "axm_home",
    "delete",
    "get",
    "load",
    "resolve_safe",
    "set_",
    "validate_segment",
]
