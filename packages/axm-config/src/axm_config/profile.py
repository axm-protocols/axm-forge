from __future__ import annotations

import os
import re
from pathlib import Path

from axm_config.home import axm_home_path
from axm_config.resolver import ConfigError

__all__ = [
    "DEFAULT_PROFILE",
    "PROFILE_ENV_VAR",
    "current_profile",
    "profile_config_path",
    "profile_env",
    "profile_root",
    "profile_root_for",
]

PROFILE_ENV_VAR = "AXM_PROFILE"
DEFAULT_PROFILE = "production"

_PROFILE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def validate_profile_name(name: str) -> str:
    """Return a valid profile name or raise :class:`ConfigError`."""
    if not _PROFILE_RE.fullmatch(name):
        msg = f"invalid profile {name!r}: must match {_PROFILE_RE.pattern}"
        raise ConfigError(msg)
    return name


def current_profile() -> str:
    """Return the active, lexically validated state profile."""
    profile = os.environ.get(PROFILE_ENV_VAR) or DEFAULT_PROFILE
    return validate_profile_name(profile)


def profile_root() -> Path | None:
    """Return the isolated state root, or None for production."""
    return profile_root_for(current_profile())


def profile_root_for(profile: str) -> Path | None:
    """Return the state root of ``profile``, or None for the default one.

    The named counterpart of :func:`profile_root`: it answers for an arbitrary
    profile instead of the active one, so a caller can ask what a profile
    *would* use without mutating ``AXM_PROFILE``. Pure computation -- the root
    hangs below :func:`axm_home_path`, so no directory is created, and the
    deliberate asymmetry is preserved: ``AXM_HOME`` only selects the
    ``config.toml`` that is read, never this convention.
    """
    validated = validate_profile_name(profile)
    if validated == DEFAULT_PROFILE:
        return None
    return axm_home_path() / "profiles" / validated


def profile_config_path() -> Path:
    """Return the config store path for the active profile."""
    root = profile_root()
    if root is None:
        return axm_home_path() / "config.toml"
    return root / "config.toml"


def profile_env() -> dict[str, str]:
    """Return the environment overlay that propagates the active profile."""
    return {PROFILE_ENV_VAR: current_profile()}
