from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from axm_config.profile import current_profile

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
    selected_profile = profile if profile is not None else current_profile()
    home = _home_path()
    root = home / "profiles" / selected_profile
    paths = _profile_paths(root)
    isolated, escapes = is_isolated(root, paths)
    return ProfileIsolation(
        profile=selected_profile,
        profile_root=root,
        paths=paths,
        isolated=isolated,
        escapes=escapes,
    )


def _home_path() -> Path:
    configured = os.environ.get(_HOME_ENV_VAR)
    if configured is not None:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".axm").resolve()


def _profile_paths(root: Path) -> dict[str, Path]:
    return {
        "tickets_db": root / "tickets" / "tickets.db",
        "warden_socket": root / "warden.sock",
        "warden_log": root / "warden.log",
        "sessions_root": root / "sessions",
        "quality_dir": root / "quality",
        "protocols_dir": root / "protocols",
    }
