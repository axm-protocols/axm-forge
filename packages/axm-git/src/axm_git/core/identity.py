"""Git identity resolution with schedule-based profile switching."""

from __future__ import annotations

import logging
import tomllib
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel

__all__ = [
    "GitIdentity",
    "GitProfileConfig",
    "author_args",
    "load_config",
    "resolve_identity",
]

logger = logging.getLogger(__name__)

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


class GitIdentity(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel exposes Any in its API
    """A git author identity."""

    name: str
    email: str


class ScheduleRule(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel exposes Any in its API
    """A time-based rule mapping to a profile."""

    profile: str
    days: list[str]
    start: str
    end: str


class Schedule(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel exposes Any in its API
    """Schedule configuration with rules."""

    rules: list[ScheduleRule] = []


class GitProfileConfig(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel exposes Any in its API
    """Full git-profiles.toml configuration."""

    default: GitIdentity
    profiles: dict[str, GitIdentity] = {}
    schedule: Schedule = Schedule()
    workspace_paths: list[Path] = []
    timezone: str = "Europe/Paris"


def load_config(config_path: Path | None = None) -> GitProfileConfig | None:
    """Load and validate a git-profiles TOML config file.

    File-absent returns ``None`` silently. File-present-but-malformed
    returns ``None`` and emits a ``WARNING`` referencing *path* and the
    exception class. After successful parse, also warns when
    ``schedule.rules`` is non-empty but ``workspace_paths`` is empty
    (governance config is configured but cannot apply).
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning(
            "Cannot read git-profiles config at %s: %s", path, exc.__class__.__name__
        )
        return None
    if not data:
        return None
    try:
        parsed: dict[str, object] = tomllib.loads(data.decode())
        config = GitProfileConfig.model_validate(parsed)
    except (tomllib.TOMLDecodeError, ValueError, KeyError) as exc:
        logger.warning(
            "Invalid git-profiles config at %s: %s", path, exc.__class__.__name__
        )
        return None
    if config.schedule.rules and not config.workspace_paths:
        logger.warning(
            "git-profiles config at %s defines schedule.rules but "
            "workspace_paths is empty — schedule is inert",
            path,
        )
    return config


def _matches_schedule(rule: ScheduleRule, now: datetime) -> bool:
    """Check if *now* falls within the rule's day + time window.

    Start is inclusive, end is exclusive. Accepts both naive and
    tz-aware ``datetime``; the schedule windows are expressed in
    wall-clock time of *now*.
    """
    weekday = now.weekday()
    if weekday not in [_DAY_MAP[d] for d in rule.days]:
        return False
    current_time = now.time()
    start = time.fromisoformat(rule.start)
    end = time.fromisoformat(rule.end)
    return start <= current_time < end


def _is_axm_workspace(path: Path, workspace_paths: list[Path]) -> bool:
    """Return ``True`` if *path* resolves under any of *workspace_paths*.

    Empty *workspace_paths* always returns ``False``.
    """
    if not workspace_paths:
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in workspace_paths:
        try:
            resolved.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        return True
    return False


def resolve_by_override(
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


def resolve_by_schedule(
    config: GitProfileConfig,
    workspace_path: Path,
    now: datetime,
) -> GitIdentity | None:
    """Resolve identity from schedule rules for AXM workspaces.

    Returns ``None`` when the path is outside AXM workspaces or no
    schedule rule matches.
    """
    if not _is_axm_workspace(workspace_path, config.workspace_paths):
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

    override = resolve_by_override(config, profile_override)
    if profile_override is not None:
        return override

    tz = ZoneInfo(config.timezone)
    if now is None:
        effective_now = datetime.now(tz=tz)
    elif now.tzinfo is None:
        effective_now = now
    else:
        effective_now = now.astimezone(tz)
    return resolve_by_schedule(config, workspace_path, effective_now) or config.default


def author_args(identity: GitIdentity | None) -> list[str]:
    """Build ``--author`` arguments for a git command."""
    if identity is None:
        return []
    return ["--author", f"{identity.name} <{identity.email}>"]
