"""Session sandbox: redirect the six AXM state paths to an ephemeral root.

The sandbox lives entirely in the inherited environment (``AXM_SANDBOX_*``
keys), never in module state, so a child process spawned while a sandbox is
active reconstructs the same sandbox and the same launch profile. In any
process where ``AXM_SANDBOX_ROOT`` is absent, :func:`active_sandbox` returns
``None`` and every resolver behaves exactly as before.

This module must not import :mod:`axm_config.paths` nor
:mod:`axm_config.profile`: ``profile.current_profile`` depends on it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path

from axm_config.resolver import ConfigError

__all__ = [
    "SANDBOX_ROOT_ENV",
    "SandboxEscapeError",
    "SessionSandbox",
    "activate_sandbox",
    "active_sandbox",
    "deactivate_sandbox",
]

SANDBOX_ROOT_ENV = "AXM_SANDBOX_ROOT"
_LAUNCH_HOME_ENV = "AXM_SANDBOX_LAUNCH_HOME"
_LAUNCH_PROFILE_ENV = "AXM_SANDBOX_LAUNCH_PROFILE"
_LAUNCH_AXM_HOME_ENV = "AXM_SANDBOX_LAUNCH_AXM_HOME"
_PROFILE_ENV = "AXM_PROFILE"
_RESTORED_KEYS = (
    SANDBOX_ROOT_ENV,
    _LAUNCH_HOME_ENV,
    _LAUNCH_PROFILE_ENV,
    _LAUNCH_AXM_HOME_ENV,
    _PROFILE_ENV,
)
# The launch variables of the six sandboxed state paths.
_GUARDED_VARIABLES = (
    "AXM_PATHS_SESSIONS_ROOT",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_WARDEN_SOCKET",
    "AXM_TICKETS_DB_PATH",
    "AXM_WARDEN_LOG_PATH",
)


class SandboxEscapeError(ConfigError):
    """A launch variable points a sandboxed path at the real AXM state."""


@dataclass(frozen=True)
class SessionSandbox:
    """An active session sandbox and the launch values it was built from.

    ``previous`` records the ``AXM_SANDBOX_*`` and ``AXM_PROFILE`` values seen
    at activation so :func:`deactivate_sandbox` can restore them exactly
    (nested in-process sessions). It is empty on a sandbox reconstructed from
    the environment by :func:`active_sandbox`.
    """

    root: Path
    launch_home: Path
    launch_profile: str | None
    launch_axm_home: str | None
    previous: tuple[tuple[str, str | None], ...] = field(
        default=(), compare=False, repr=False
    )


def _environ(environ: MutableMapping[str, str] | None) -> MutableMapping[str, str]:
    return os.environ if environ is None else environ


def _home_of(environ: Mapping[str, str]) -> Path:
    raw = environ.get("HOME")
    return Path(raw) if raw else Path.home()


def _refuse_escapes(environ: Mapping[str, str], home: Path) -> None:
    """Raise when a launch variable resolves at or under HOME/axm or HOME/.axm."""
    resolved_home = home.expanduser().resolve()
    forbidden = (resolved_home / "axm", resolved_home / ".axm")
    for variable in _GUARDED_VARIABLES:
        value = environ.get(variable)
        if not value:
            continue
        resolved = Path(value).expanduser().resolve()
        for base in forbidden:
            if resolved.is_relative_to(base):
                msg = (
                    f"{variable}={value} escapes the session sandbox: "
                    f"it resolves to {resolved}, under the real AXM state {base}"
                )
                raise SandboxEscapeError(msg)


def active_sandbox(
    environ: MutableMapping[str, str] | None = None,
) -> SessionSandbox | None:
    """Return the sandbox published in ``environ``, or ``None`` when inactive."""
    env = _environ(environ)
    root = env.get(SANDBOX_ROOT_ENV)
    if not root:
        return None
    launch_home = env.get(_LAUNCH_HOME_ENV)
    return SessionSandbox(
        root=Path(root),
        launch_home=Path(launch_home) if launch_home else Path.home(),
        launch_profile=env.get(_LAUNCH_PROFILE_ENV) or None,
        launch_axm_home=env.get(_LAUNCH_AXM_HOME_ENV) or None,
    )


def activate_sandbox(
    root: Path,
    environ: MutableMapping[str, str] | None = None,
) -> SessionSandbox:
    """Publish a sandbox on ``root`` in ``environ`` and strip ``AXM_PROFILE``.

    Raises :class:`SandboxEscapeError` when one of the six launch variables
    resolves at or under ``<HOME>/axm`` or ``<HOME>/.axm``. Creates no
    directory: the caller owns the root.
    """
    env = _environ(environ)
    launch_home = _home_of(env)
    _refuse_escapes(env, launch_home)
    outer = active_sandbox(env)
    launch_profile = env.get(_PROFILE_ENV) or (
        outer.launch_profile if outer is not None else None
    )
    launch_axm_home = env.get("AXM_HOME") or None
    sandbox = SessionSandbox(
        root=Path(root),
        launch_home=launch_home,
        launch_profile=launch_profile,
        launch_axm_home=launch_axm_home,
        previous=tuple((key, env.get(key)) for key in _RESTORED_KEYS),
    )
    env[SANDBOX_ROOT_ENV] = str(root)
    env[_LAUNCH_HOME_ENV] = str(launch_home)
    env[_LAUNCH_PROFILE_ENV] = launch_profile or ""
    env[_LAUNCH_AXM_HOME_ENV] = launch_axm_home or ""
    env.pop(_PROFILE_ENV, None)
    return sandbox


def deactivate_sandbox(
    sandbox: SessionSandbox,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Restore the environment ``sandbox`` replaced at activation."""
    env = _environ(environ)
    previous = sandbox.previous or (
        *((key, None) for key in _RESTORED_KEYS[:-1]),
        (_PROFILE_ENV, sandbox.launch_profile),
    )
    for key, value in previous:
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
