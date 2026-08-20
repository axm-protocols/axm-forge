"""Shared filesystem roots, owned by ``axm-config`` and only *read* elsewhere.

The galaxy declared the same roots over and over: ``~/axm/sessions`` in five
packages, ``~/axm/quality`` in three, ``~/axm/protocols`` in three, and the
``~/.axm/warden.sock`` resolution copy-pasted across four sites in two repos.
Each copy is a place the value can silently drift. This module is the single
owner: consumers call a getter here instead of rebuilding ``Path.home() / ...``.

Two properties make adoption safe, and they are the whole point:

* **The default stays in the caller's code.** Every getter takes the caller's
  current constant as ``default``, so with no ``~/.axm/config.toml`` the
  resolved value is byte-for-byte what it is today. Wiring a package up is
  therefore purely additive -- no behaviour changes until someone actually
  configures a path.
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
import tomllib
from pathlib import Path
from typing import cast

from axm_config.home import resolve_safe
from axm_config.resolver import ConfigError, resolve

__all__ = [
    "PATHS_NAMESPACE",
    "get_bool",
    "get_int",
    "get_path",
    "get_str",
    "protocols_dir",
    "quality_dir",
    "sessions_root",
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


def get_path(
    key: str,
    default: Path,
    *,
    namespace: str = PATHS_NAMESPACE,
) -> Path:
    """Resolve ``key`` in ``[paths]`` as a normalised :class:`~pathlib.Path`.

    ``default`` is the caller's existing constant and is returned **unchanged**
    when nothing is configured -- neither expanded nor validated -- so wiring a
    consumer up cannot alter today's behaviour.

    A configured value (env or file) is expanded (``~``), resolved to an
    absolute path, and refused via :func:`resolve_safe` if it sits inside a git
    checkout. Raises :class:`ConfigError` on a non-string/non-path value or an
    in-repo path, so a bad config fails loudly at the boundary rather than
    writing runtime state somewhere unintended.
    """
    configured = _resolve_configured(namespace, key)
    if configured is _MISSING:
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


def sessions_root(*, default: Path | None = None) -> Path:
    """The loom sessions root -- where runs write manifests, traces, artifacts.

    Declared identically in ``axm-loom``, ``axm-knowledge`` and ``axm-orison``
    (whose docstrings already say they *mirror* loom); this is the seam those
    three delegate to. ``default`` overrides the built-in ``~/axm/sessions``
    for a caller that must keep its own constant during migration.
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
