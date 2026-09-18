from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from axm_config.home import axm_home_path
from axm_config.paths import (
    protocols_dir,
    quality_dir,
    sessions_root,
    tickets_db,
    warden_log_path,
    warden_socket,
)
from axm_config.profile import current_profile, validate_profile_name

__all__ = ["ProfileIsolation", "is_isolated", "profile_isolation"]

_HOME_ENV_VAR = "AXM_HOME"


class ProfileIsolation(BaseModel):  # type: ignore[explicit-any]
    """Resolved state paths and their isolation verdict for one profile."""

    profile: str
    profile_root: Path
    paths: dict[str, Path]
    isolated: bool
    escapes: list[str]


def is_isolated(
    root: Path,
    paths: Mapping[str, Path],
) -> tuple[bool, list[str]]:
    """Return whether every named path is contained by the root."""
    escapes = sorted(
        key for key, path in paths.items() if not path.is_relative_to(root)
    )
    return not escapes, escapes


def profile_isolation(profile: str | None = None) -> ProfileIsolation:
    """Resolve a profile's state paths without creating filesystem entries."""
    selected_profile = (
        validate_profile_name(profile) if profile is not None else current_profile()
    )
    root = axm_home_path() / "profiles" / selected_profile
    paths = _profile_paths(selected_profile)
    isolated, escapes = is_isolated(root, paths)
    return ProfileIsolation(
        profile=selected_profile,
        profile_root=root,
        paths=paths,
        isolated=isolated,
        escapes=escapes,
    )


def _profile_paths(profile: str) -> dict[str, Path]:
    return {
        "tickets_db": tickets_db(profile=profile),
        "warden_socket": warden_socket(profile=profile),
        "warden_log": warden_log_path(profile=profile),
        "sessions_root": sessions_root(profile=profile),
        "quality_dir": quality_dir(profile=profile),
        "protocols_dir": protocols_dir(profile=profile),
    }
