"""Git identity resolution with schedule-based profile switching."""

from __future__ import annotations

import tomllib
from datetime import datetime, time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

__all__ = [
    "GitIdentity",
    "GitProfileConfig",
    "author_args",
    "load_config",
    "resolve_identity",
]

_AXM_WORKSPACE_PREFIX = "/Users/gabriel/Documents/Code/python/axm-workspaces/axm-"
_DEFAULT_CONFIG_PATH = Path.home() / "axm" / "git-profiles.toml"

_DAY_MAP: dict[str, int] = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class GitIdentity(BaseModel):
    """A git author identity."""

    name: str
    email: str


class ScheduleRule(BaseModel):
    """A time-based rule mapping to a profile."""

    profile: str
    days: list[str]
    start: str
    end: str


class Schedule(BaseModel):
    """Schedule configuration with rules."""

    rules: list[ScheduleRule] = []


class GitProfileConfig(BaseModel):
    """Full git-profiles.toml configuration."""

    default: GitIdentity
    profiles: dict[str, GitIdentity] = {}
    schedule: Schedule = Schedule()


def load_config(config_path: Path | None = None) -> GitProfileConfig | None:
    """Load and validate a git-profiles TOML config file.

    Returns ``None`` if the file is missing, empty, or invalid.
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    try:
        data = path.read_bytes()
        if not data:
            return None
        parsed: dict[str, Any] = tomllib.loads(data.decode())
        return GitProfileConfig.model_validate(parsed)
    except (OSError, tomllib.TOMLDecodeError, ValueError, KeyError):
        return None


def _matches_schedule(rule: ScheduleRule, now: datetime) -> bool:
    """Check if *now* falls within the rule's day + time window.

    Start is inclusive, end is exclusive.
    """
    weekday = now.weekday()
    if weekday not in [_DAY_MAP[d] for d in rule.days]:
        return False
    current_time = now.time()
    start = time.fromisoformat(rule.start)
    end = time.fromisoformat(rule.end)
    return start <= current_time < end


def _is_axm_workspace(path: Path) -> bool:
    """Return ``True`` if *path* resolves under an axm workspace."""
    resolved = str(path.resolve())
    return resolved.startswith(_AXM_WORKSPACE_PREFIX)


def _resolve_by_override(
    config: GitProfileConfig,
    profile_override: str | None,
) -> GitIdentity | None:
    """Resolve identity from an explicit profile override.

    Returns the matching identity, or ``None`` when *profile_override*
    is ``None`` or names an unknown profile.
    """
    if profile_override is None:
        return None
    if profile_override == "default":
        return config.default
    return config.profiles.get(profile_override)


def _resolve_by_schedule(
    config: GitProfileConfig,
    workspace_path: Path,
    now: datetime,
) -> GitIdentity | None:
    """Resolve identity from schedule rules for AXM workspaces.

    Returns ``None`` when the path is outside AXM workspaces or no
    schedule rule matches.
    """
    if not _is_axm_workspace(workspace_path):
        return None
    for rule in config.schedule.rules:
        if _matches_schedule(rule, now) and rule.profile in config.profiles:
            return config.profiles[rule.profile]
    return None


def resolve_identity(
    workspace_path: Path,
    *,
    now: datetime | None = None,
    profile_override: str | None = None,
    config_path: Path | None = None,
) -> GitIdentity | None:
    """Resolve the git identity for the given workspace.

    Returns ``None`` when no config is available or an unknown profile
    is requested via *profile_override*.
    """
    config = load_config(config_path)
    if config is None:
        return None

    override = _resolve_by_override(config, profile_override)
    if profile_override is not None:
        return override

    effective_now = now or datetime.now()
    return _resolve_by_schedule(config, workspace_path, effective_now) or config.default


def author_args(identity: GitIdentity | None) -> list[str]:
    """Build ``--author`` arguments for a git command."""
    if identity is None:
        return []
    return ["--author", f"{identity.name} <{identity.email}>"]
