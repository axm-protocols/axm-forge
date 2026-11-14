"""Compatibility policy for explicit and historical warden socket selectors.

Owned here so consumers never parse TOML or mutate environment to validate paths.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import cast

from axm_config.home import resolve_safe
from axm_config.paths import warden_socket
from axm_config.profile import current_profile, profile_root
from axm_config.resolver import ConfigError

__all__ = ["resolve_socket_path"]

_HISTORICAL_SOCKET_ENV = "AXM_WARDEN_SOCKET"
_CONFIG_SOCKET_ENV = "AXM_PATHS_WARDEN_SOCKET"


def _override_profile_root() -> Path | None:
    """Return the isolated profile root for an explicit AXM_HOME override."""
    home = os.environ.get("AXM_HOME")
    profile = current_profile()
    if home is None or profile == "production":
        return None
    return Path(home) / "profiles" / profile


def _validate_override_candidate(candidate: Path, root: Path) -> Path:
    """Apply the upstream safe-path rule and profile containment to a candidate."""
    try:
        resolved = resolve_safe(candidate.expanduser())
    except ValueError as exc:
        msg = f"invalid path for paths.warden_socket: {exc}"
        raise ConfigError(msg) from exc
    resolved_root = root.expanduser().resolve()
    if not resolved.is_relative_to(resolved_root):
        profile = current_profile()
        msg = (
            f"invalid path for paths.warden_socket: profile {profile!r} "
            f"requires containment under {resolved_root}, got {resolved}"
        )
        raise ConfigError(msg)
    return candidate


def _override_store_candidate(root: Path) -> Path | None:
    """Read the isolated profile store selected by an explicit AXM_HOME."""
    config_path = root / "config.toml"
    try:
        with config_path.open("rb") as stream:
            document = cast("dict[str, object]", tomllib.load(stream))
    except FileNotFoundError:
        return None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"cannot load configuration from {config_path}: {exc}"
        raise ConfigError(msg) from exc
    section = document.get("paths")
    if not isinstance(section, dict):
        return None
    configured = cast("dict[str, object]", section).get("warden_socket")
    if configured is None:
        return None
    if not isinstance(configured, str):
        msg = (
            "invalid path for paths.warden_socket: expected a string, "
            f"got {type(configured).__name__}"
        )
        raise ConfigError(msg)
    return Path(configured)


def _validate_candidate(candidate: Path, override_root: Path | None) -> Path:
    if override_root is not None:
        return _validate_override_candidate(candidate, override_root)
    return _guard_candidate(candidate)


def _guard_candidate(candidate: Path) -> Path:
    """Validate an explicit candidate through axm-config's path guard."""
    root = profile_root()
    if root is not None:
        return _validate_override_candidate(candidate, root)
    try:
        resolve_safe(candidate.expanduser())
    except ValueError as exc:
        raise ConfigError(f"invalid path for paths.warden_socket: {exc}") from exc
    return candidate


def resolve_socket_path(socket: Path | None = None) -> Path:
    """Resolve every socket source through the upstream profile-aware guard."""
    override_root = _override_profile_root()
    if socket is not None:
        return _validate_candidate(socket, override_root)
    historical = os.environ.get(_HISTORICAL_SOCKET_ENV)
    if historical is not None:
        return _validate_candidate(Path(historical), override_root)
    if override_root is None:
        return warden_socket()
    derived = os.environ.get(_CONFIG_SOCKET_ENV)
    candidate = (
        Path(derived)
        if derived is not None
        else _override_store_candidate(override_root)
    )
    return _validate_override_candidate(
        candidate if candidate is not None else override_root / "warden.sock",
        override_root,
    )
