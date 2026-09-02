"""Shared filesystem roots, owned by ``axm-config`` and only *read* elsewhere.

The galaxy declared the same roots over and over: ``~/axm/sessions`` in five
packages, ``~/axm/quality`` in three, ``~/axm/protocols`` in three, and the
``~/.axm/warden.sock`` resolution copy-pasted across four sites in two repos.
Each copy is a place the value can silently drift. This module is the single
owner: consumers call a getter here instead of rebuilding ``Path.home() / ...``.

Two properties make adoption safe, and they are the whole point:

* **Production keeps the caller's default.** Without an active profile, every
  getter returns the caller's current constant byte-for-byte when no value is
  configured. Under a non-production profile, the default branch is instead
  rooted below ``~/.axm/profiles/<profile>/`` so state is isolated by default.
  Configured environment and file values keep their higher precedence.
* **Normalisation happens here, once.** :func:`get_path` turns the resolver's
  raw value (an env var is always a ``str``; a TOML value keeps its parsed
  type) into an expanded, resolved :class:`~pathlib.Path`. If each consumer
  did its own ``Path(...)``/``expanduser()``, the duplication would simply move
  up one level instead of disappearing.

Precedence is the resolver's own ``env > file > default``, so an existing
override such as ``AXM_PATHS_WARDEN_SOCKET`` keeps working unchanged.

Security: a *configured* path is passed through
:func:`axm_config.home.resolve_safe`, which refuses anything resolving inside a
git checkout -- runtime state (session traces, quality reports, a socket) must
never land in a repo where it can be committed. The **default is never
checked**: it is code, not user input, and validating it would turn a
working installation into a failing one, breaking the additive guarantee above.
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import cast

from axm_config.home import axm_home, resolve_safe
from axm_config.profile import profile_root
from axm_config.resolver import ConfigError, resolve

__all__ = [
    "PATHS_NAMESPACE",
    "get_bool",
    "get_int",
    "get_path",
    "get_str",
    "inference_base_url",
    "inference_model",
    "inference_origin",
    "protocols_dir",
    "quality_dir",
    "sessions_root",
    "tickets_db",
    "warden_autostart",
    "warden_binary_path",
    "warden_log_path",
    "warden_max_concurrent",
    "warden_mode",
    "warden_park_threshold",
    "warden_socket",
]

#: The namespace every shared root lives under -- ``[paths]`` in
#: ``~/.axm/config.toml``, ``AXM_PATHS_<KEY>`` in the environment.
PATHS_NAMESPACE = "paths"

_MISSING = object()


def _resolve_configured(namespace: str, key: str) -> object:
    """Resolve a value, honoring an explicitly isolated AXM home."""
    configured = resolve(namespace, key, _MISSING)
    if configured is not _MISSING:
        return configured

    home_override = os.environ.get("AXM_HOME")
    if home_override is None:
        return _MISSING
    config_path = Path(home_override) / "config.toml"
    try:
        with config_path.open("rb") as stream:
            document = tomllib.load(stream)
    except FileNotFoundError:
        return _MISSING
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"cannot load configuration from {config_path}: {exc}"
        raise ConfigError(msg) from exc

    section = document.get(namespace)
    if not isinstance(section, dict):
        return _MISSING
    return cast(object, section.get(key, _MISSING))


_PROFILE_RELATIVE_PATHS = {
    (PATHS_NAMESPACE, "sessions_root"): Path("sessions"),
    (PATHS_NAMESPACE, "quality_dir"): Path("quality"),
    (PATHS_NAMESPACE, "protocols_dir"): Path("protocols"),
    ("warden", "log_path"): Path("warden.log"),
    (PATHS_NAMESPACE, "warden_socket"): Path("warden.sock"),
}


def get_path(
    key: str,
    default: Path,
    *,
    namespace: str = PATHS_NAMESPACE,
) -> Path:
    """Resolve ``key`` in ``[paths]`` as a normalised :class:`~pathlib.Path`.

    ``default`` is the caller's existing constant. In production it is returned
    **unchanged** when nothing is configured. For the state paths registered in
    ``_PROFILE_RELATIVE_PATHS``, a non-production profile replaces that fallback
    with a path rooted below :func:`profile_root`.

    A configured value (env or file) is expanded (``~``), resolved to an
    absolute path, and refused via :func:`resolve_safe` if it sits inside a git
    checkout. Raises :class:`ConfigError` on a non-string/non-path value or an
    in-repo path, so a bad config fails loudly at the boundary rather than
    writing runtime state somewhere unintended.
    """
    configured = _resolve_configured(namespace, key)
    if configured is _MISSING:
        root = profile_root()
        relative = _PROFILE_RELATIVE_PATHS.get((namespace, key))
        if root is not None and relative is not None:
            return root / relative
        return default
    if not isinstance(configured, str | Path):
        msg = (
            f"invalid path for {namespace}.{key}: "
            f"expected a string, got {type(configured).__name__}"
        )
        raise ConfigError(msg)
    expanded = Path(configured).expanduser()
    try:
        return resolve_safe(expanded)
    except ValueError as exc:
        msg = f"invalid path for {namespace}.{key}: {exc}"
        raise ConfigError(msg) from exc


def get_int(
    key: str,
    default: int,
    *,
    namespace: str = PATHS_NAMESPACE,
) -> int:
    """Resolve a configured integer while preserving an untouched default."""
    configured = _resolve_configured(namespace, key)
    if configured is _MISSING:
        return default
    if type(configured) is int:
        return configured
    if isinstance(configured, str):
        try:
            return int(configured)
        except ValueError as exc:
            msg = f"invalid integer for {namespace}.{key}: {configured!r}"
            raise ConfigError(msg) from exc
    msg = (
        f"invalid integer for {namespace}.{key}: "
        f"expected an integer, got {type(configured).__name__}"
    )
    raise ConfigError(msg)


def get_bool(
    key: str,
    default: bool,
    *,
    namespace: str = PATHS_NAMESPACE,
) -> bool:
    """Resolve a configured boolean while preserving an untouched default."""
    configured = _resolve_configured(namespace, key)
    if configured is _MISSING:
        return default
    if isinstance(configured, bool):
        return configured
    if isinstance(configured, str):
        normalised = configured.lower()
        if normalised in {"1", "true", "yes", "on"}:
            return True
        if normalised in {"0", "false", "no", "off"}:
            return False
    msg = f"invalid boolean for {namespace}.{key}: {configured!r}"
    raise ConfigError(msg)


_INFERENCE_NAMESPACE = "inference"
_DEFAULT_INFERENCE_BASE_URL = "http://127.0.0.1:8000/v1"
_DEFAULT_INFERENCE_MODEL = "ornith-ai/Ornith-1.5-9B-MLX-4bit"
_DEFAULT_INFERENCE_ORIGIN = "local"
_INFERENCE_ORIGINS = frozenset({"anthropic", "google", "local", "openai"})


def get_str(
    key: str,
    default: str,
    *,
    namespace: str = PATHS_NAMESPACE,
) -> str:
    """Resolve a configured value as text while preserving an untouched default."""
    configured = _resolve_configured(namespace, key)
    if configured is _MISSING:
        return default
    return str(configured)


def inference_origin() -> str:
    """Return the configured inference provider origin."""
    value = get_str(
        "origin",
        _DEFAULT_INFERENCE_ORIGIN,
        namespace=_INFERENCE_NAMESPACE,
    )
    if value not in _INFERENCE_ORIGINS:
        expected = ", ".join(sorted(_INFERENCE_ORIGINS))
        msg = (
            "invalid value for inference.origin: "
            f"expected one of {expected}, got {value!r}"
        )
        raise ConfigError(msg)
    return value


def inference_base_url() -> str:
    """Return the configured inference engine address unchanged."""
    return get_str(
        "base_url",
        _DEFAULT_INFERENCE_BASE_URL,
        namespace=_INFERENCE_NAMESPACE,
    )


def inference_model() -> str:
    """Return the configured inference model identifier unchanged."""
    return get_str(
        "model",
        _DEFAULT_INFERENCE_MODEL,
        namespace=_INFERENCE_NAMESPACE,
    )


def sessions_root(*, default: Path | None = None) -> Path:
    """The loom sessions root -- where runs write manifests, traces, artifacts.

    Declared identically in ``axm-loom``, ``axm-knowledge`` and ``axm-orison``
    (whose docstrings already say they *mirror* loom); this is the seam those
    three delegate to. In production, ``default`` overrides the built-in
    ``~/axm/sessions`` for callers retaining their migration constant; an
    active non-production profile instead owns the unconfigured state root.
    """
    fallback = default if default is not None else Path.home() / "axm" / "sessions"
    return get_path("sessions_root", default=fallback)


def quality_dir(*, default: Path | None = None) -> Path:
    """The quality-trace directory written by ``axm-audit`` / ``axm-init``."""
    fallback = default if default is not None else Path.home() / "axm" / "quality"
    return get_path("quality_dir", default=fallback)


def protocols_dir(*, default: Path | None = None) -> Path:
    """The legacy YAML protocol directory read by the engine and briefings."""
    fallback = default if default is not None else Path.home() / "axm" / "protocols"
    return get_path("protocols_dir", default=fallback)


_WARDEN_NAMESPACE = "warden"
_DEFAULT_WARDEN_PARK_THRESHOLD = 3
_DEFAULT_WARDEN_MODE = "embedded"
_DEFAULT_WARDEN_MAX_CONCURRENT = 4
_DEFAULT_WARDEN_AUTOSTART = True
_WARDEN_MODES = frozenset({"embedded", "pull"})


def warden_mode(*, default: str | None = None) -> str:
    """Return the configured warden execution mode."""
    fallback = default if default is not None else _DEFAULT_WARDEN_MODE
    configured = _resolve_configured(_WARDEN_NAMESPACE, "mode")
    if configured is _MISSING:
        return fallback

    value = get_str("mode", fallback, namespace=_WARDEN_NAMESPACE)
    if value not in _WARDEN_MODES:
        expected = ", ".join(sorted(_WARDEN_MODES))
        msg = (
            f"invalid value for warden.mode: expected one of {expected}, got {value!r}"
        )
        raise ConfigError(msg)
    return value


def warden_max_concurrent(*, default: int | None = None) -> int:
    """Return the strictly positive warden concurrency limit."""
    fallback = default if default is not None else _DEFAULT_WARDEN_MAX_CONCURRENT
    configured = _resolve_configured(_WARDEN_NAMESPACE, "max_concurrent")
    if configured is _MISSING:
        return fallback

    value = get_int("max_concurrent", fallback, namespace=_WARDEN_NAMESPACE)
    if value <= 0:
        msg = f"invalid value for warden.max_concurrent: expected > 0, got {value}"
        raise ConfigError(msg)
    return value


def warden_park_threshold(*, default: int | None = None) -> int:
    """Return the minimum number of failed generations before parking."""
    fallback = default if default is not None else _DEFAULT_WARDEN_PARK_THRESHOLD
    configured = _resolve_configured(_WARDEN_NAMESPACE, "park_threshold")
    if configured is _MISSING:
        return fallback

    value = get_int("park_threshold", fallback, namespace=_WARDEN_NAMESPACE)
    if value < 1:
        msg = f"invalid value for warden.park_threshold: expected >= 1, got {value}"
        raise ConfigError(msg)
    return value


def warden_autostart(*, default: bool | None = None) -> bool:
    """Return whether consumers should start the warden automatically."""
    fallback = default if default is not None else _DEFAULT_WARDEN_AUTOSTART
    return get_bool("autostart", fallback, namespace=_WARDEN_NAMESPACE)


def warden_binary_path(*, default: Path | None = None) -> Path:
    """Return the configured or interpreter-relative warden executable path."""
    fallback = (
        default if default is not None else Path(sys.executable).parent / "axm-warden"
    )
    return get_path("binary_path", fallback, namespace=_WARDEN_NAMESPACE)


def warden_log_path(*, default: Path | None = None) -> Path:
    """Return the configured or AXM-home-relative warden log path."""
    fallback = default if default is not None else axm_home() / "warden.log"
    return get_path("log_path", fallback, namespace=_WARDEN_NAMESPACE)


def tickets_db(*, default: Path | None = None) -> Path:
    """Return the ticket database path for the active state profile."""
    active_root = profile_root()
    if default is not None:
        fallback = default
    elif active_root is None:
        fallback = Path.home() / "axm" / "tickets" / "tickets.db"
    else:
        fallback = active_root / "tickets" / "tickets.db"
    return get_path("db_path", default=fallback, namespace="tickets")


def warden_socket(*, default: Path | None = None) -> Path:
    """The warden control-plane socket bound by ``axm-warden serve``.

    Note the precedence a consumer must preserve. Callers layer an *explicit
    argument* on top of this (``--socket`` on the CLI, the ``socket=`` kwarg on
    the tools), which outranks everything here; this function covers only the
    ``env > file > default`` tail below it. Collapsing the explicit argument
    into the config lookup would silently change behaviour, so callers keep
    their own ``if socket is not None: return socket`` guard and delegate the
    rest.
    """
    fallback = default if default is not None else Path.home() / ".axm" / "warden.sock"
    return get_path("warden_socket", default=fallback)
