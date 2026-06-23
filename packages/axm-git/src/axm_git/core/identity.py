"""Git identity resolution with schedule-based profile switching."""

from __future__ import annotations

import logging
import tomllib
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import axm_config
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


def _legacy_config_path() -> Path:
    """Resolve the legacy ``~/axm/git-profiles.toml`` path at call time.

    Resolved lazily (not the module-level constant) so an overridden ``HOME``
    is honoured — the constant is frozen at import. Kept for the transitional
    AC3 fallback only.
    """
    return Path.home() / "axm" / "git-profiles.toml"


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

    enabled: bool = True
    rules: list[ScheduleRule] = []


class GitProfileConfig(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel exposes Any in its API
    """Full git-profiles.toml configuration."""

    default: GitIdentity
    profiles: dict[str, GitIdentity] = {}
    schedule: Schedule = Schedule()
    workspace_paths: list[Path] = []
    timezone: str = "Europe/Paris"


def _warn_inert_schedule(config: GitProfileConfig, source: str) -> None:
    """Warn when schedule rules are set but no workspace_paths can apply them."""
    if config.schedule.rules and not config.workspace_paths:
        logger.warning(
            "git-profiles config at %s defines schedule.rules but "
            "workspace_paths is empty — schedule is inert",
            source,
        )


def _load_from_file(path: Path) -> GitProfileConfig | None:
    """Parse and validate a git-profiles TOML file (explicit-path/legacy form).

    File-absent returns ``None`` silently. File-present-but-malformed
    returns ``None`` and emits a ``WARNING`` referencing *path* and the
    exception class.
    """
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
    _warn_inert_schedule(config, str(path))
    return config


def _load_from_store() -> GitProfileConfig | None:
    """Build ``GitProfileConfig`` from the ``[git]`` section of the single store.

    ``workspace_paths`` is sourced from ``[echo].workspace_roots`` (single
    source of followed roots), not from ``[git]``. Returns ``None`` when the
    ``[git]`` section is absent — a present section requires at least
    ``default`` to resolve. Malformed/invalid stored data degrades to ``None``
    with a ``WARNING``.
    """
    try:
        default = axm_config.get("git", "default")
    except (ValueError, OSError) as exc:
        logger.warning(
            "Cannot read git config from store (%s) — falling back to legacy",
            exc.__class__.__name__,
        )
        return None
    if not default:
        return None
    payload: dict[str, object] = {
        "default": default,
        "profiles": axm_config.get("git", "profiles", default={}),
        "schedule": axm_config.get("git", "schedule", default={}),
        "workspace_paths": axm_config.get("echo", "workspace_roots", default=[]),
    }
    try:
        config = GitProfileConfig.model_validate(payload)
    except (ValueError, KeyError) as exc:
        logger.warning(
            "Invalid git-profiles config in store [git]: %s", exc.__class__.__name__
        )
        return None
    _warn_inert_schedule(config, "store [git]")
    return config


def load_config(config_path: Path | None = None) -> GitProfileConfig | None:
    """Load and validate git-profiles configuration.

    With an explicit *config_path*, parse that exact TOML file (unchanged
    legacy form). With ``config_path=None`` (the default), resolve from the
    ``axm_config`` single store ``[git]`` section, falling back to the legacy
    ``~/axm/git-profiles.toml`` (with a migration ``WARNING``) only while the
    store has no ``[git]`` section. Returns ``None`` when no config is
    resolvable anywhere.
    """
    if config_path is not None:
        return _load_from_file(config_path)
    from_store = _load_from_store()
    if from_store is not None:
        return from_store
    legacy_path = _legacy_config_path()
    legacy = _load_from_file(legacy_path)
    if legacy is not None:
        logger.warning(
            "Loaded git-profiles from legacy %s — migrate to the axm_config "
            "[git] section (see `axm-config`); the legacy file is transitional",
            legacy_path,
        )
    return legacy


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
    identity = config.profiles.get(profile_override)
    if identity is None:
        _warn_unknown_profile(config, profile_override)
    return identity


def _warn_unknown_profile(config: GitProfileConfig, profile_override: str) -> None:
    """Warn that *profile_override* matched no configured profile.

    Distinguishes "no profiles configured at all" (different remediation)
    from "unknown profile" (likely a typo) and surfaces the available
    profile names. Observability only — the caller still falls back to
    the default git identity.
    """
    if not config.profiles:
        logger.warning(
            "Requested git profile %r but no profiles are configured; "
            "falling back to the default identity",
            profile_override,
        )
        return
    available = ", ".join(sorted(config.profiles))
    logger.warning(
        "Unknown git profile %r; falling back to the default identity. "
        "Available profiles: %s",
        profile_override,
        available,
    )


def resolve_by_schedule(
    config: GitProfileConfig,
    workspace_path: Path,
    now: datetime,
) -> GitIdentity | None:
    """Resolve identity from schedule rules for AXM workspaces.

    Returns ``None`` when the schedule is disabled, the path is outside
    AXM workspaces, or no schedule rule matches.
    """
    if not config.schedule.enabled:
        return None
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
    is requested via *profile_override*. An unknown *profile_override*
    (a typo, or a request against an empty profile set) emits a
    ``WARNING`` naming the requested profile and the available ones
    before falling back to ``None`` — observability, not a hard failure.
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
