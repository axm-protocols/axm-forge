"""axm-config.

Non-sensitive runtime config under ~/.axm (env>file>default)
"""

from __future__ import annotations

from axm_config.home import axm_home
from axm_config.resolver import ConfigError, delete, get, load, set_

__all__ = [
    "ConfigError",
    "axm_home",
    "delete",
    "get",
    "load",
    "set_",
]
