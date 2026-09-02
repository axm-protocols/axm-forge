from __future__ import annotations

import os
import re
from pathlib import Path

from axm_config.home import axm_home
from axm_config.resolver import ConfigError

__all__ = [
    "DEFAULT_PROFILE",
    "PROFILE_ENV_VAR",
    "current_profile",
    "profile_config_path",
    "profile_env",
    "profile_root",
]

PROFILE_ENV_VAR = "AXM_PROFILE"
DEFAULT_PROFILE = "production"

_PROFILE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def current_profile() -> str:
    """Return the active, lexically validated state profile."""
    profile = os.environ.get(PROFILE_ENV_VAR) or DEFAULT_PROFILE
    if not _PROFILE_RE.fullmatch(profile):
        msg = f"invalid profile {profile!r}: must match {_PROFILE_RE.pattern}"
        raise ConfigError(msg)
    return profile


def profile_root() -> Path | None:
    """Return the isolated state root, or None for production."""
    profile = current_profile()
    if profile == DEFAULT_PROFILE:
        return None
    return axm_home() / "profiles" / profile


def profile_config_path() -> Path:
    """Return the config store path for the active profile."""
    root = profile_root()
    if root is None:
        return axm_home() / "config.toml"
    return root / "config.toml"


def profile_env() -> dict[str, str]:
    """Return the environment overlay that propagates the active profile."""
    return {PROFILE_ENV_VAR: current_profile()}
