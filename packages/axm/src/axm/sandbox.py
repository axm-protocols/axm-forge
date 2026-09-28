"""Write confinement of a subprocess: an OS sandbox wherever there is one.

A process that runs code it does not trust (a measured test suite, a replayed
gate) must not write outside the directories it was given, and must not
inherit the caller's environment. This module gives it both:

- **the sandbox** - for the whole process tree, the platform's confinement:

  - **macOS**: ``sandbox-exec`` with a profile that denies every file write
    except under the writable directories and to the character devices a
    process writes (``/dev/null``, ttys, ``/dev/fd``), then denies again any
    write under the protected paths - the last matching rule wins, so a
    protected tree inside a writable area stays read-only
    (:func:`darwin_profile`);
  - **Linux**: ``bwrap`` (bubblewrap), when installed: the root file system
    bound read-only, ``/dev`` bound as is, each writable directory bound
    writable (:func:`bubblewrap_argv`).

  Each confinement is probed with the very profile it will apply (a process
  that is itself sandboxed often cannot nest one). When none works, the
  isolation is ``detect-only`` (:data:`UNCONFINED`): the caller decides whether
  an unconfined run is acceptable, and says so in what it reports;

- **the environment** - an allow-list (:data:`INHERITED_ENV`): nothing else of
  the caller's environment reaches the process (no ``PYTHONPATH``, no
  ``FORCE_COLOR``, no credentials), and the home, temporary and XDG
  directories can be pointed into a writable directory
  (:func:`private_environment`).

:func:`run_confined` composes both for one command.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

__all__ = [
    "INHERITED_ENV",
    "PRIVATE_DIRS",
    "SANDBOX_EXEC",
    "UNCONFINED",
    "ConfinedRun",
    "Confinement",
    "Isolation",
    "bubblewrap_argv",
    "confinement",
    "darwin_profile",
    "inherited_environment",
    "private_environment",
    "run_confined",
]

type Isolation = Literal["sandbox", "detect-only"]
"""``sandbox``: writes confined by the OS; ``detect-only``: no confinement."""

SANDBOX_EXEC: Final = "/usr/bin/sandbox-exec"
"""macOS's sandbox launcher."""
_PROBE_TIMEOUT_S: Final = 30.0
_WRITABLE_DEVICES: Final = (
    '(literal "/dev/null")',
    '(literal "/dev/zero")',
    '(literal "/dev/dtracehelper")',
    '(regex #"^/dev/tty")',
    '(regex #"^/dev/fd/")',
)
INHERITED_ENV: Final = (
    "PATH",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TZ",
    "TERM",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
)
"""The only variables a confined process inherits from the caller's environment."""
PRIVATE_DIRS: Final[Mapping[str, str]] = {
    "HOME": "home",
    "USERPROFILE": "home",
    "TMPDIR": "tmp",
    "TEMP": "tmp",
    "TMP": "tmp",
    "XDG_CONFIG_HOME": "config",
    "XDG_CACHE_HOME": "cache",
    "XDG_DATA_HOME": "data",
    "XDG_STATE_HOME": "state",
}
"""Home, temporary and XDG variables -> their sub-directory of a private root."""


@dataclass(frozen=True)
class Confinement:
    """How a process is launched: the sandbox argv prefix, and what it guarantees."""

    isolation: Isolation
    prefix: tuple[str, ...] = ()
    """Prepended to the command (empty when ``detect-only``)."""

    def wrap(self, command: Sequence[str]) -> list[str]:
        """``command`` launched under this confinement."""
        return [*self.prefix, *command]


UNCONFINED: Final = Confinement(isolation="detect-only")
"""No sandbox: writes are not confined."""


def _quoted(path: Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def darwin_profile(writable: Sequence[Path], protected: Sequence[Path] = ()) -> str:
    """The ``sandbox-exec`` profile writing only under ``writable``.

    Reads are allowed; writes only under ``writable`` and to the writable
    devices; any write under ``protected`` is denied even if it lies in a
    writable area. Paths are resolved (``/tmp`` is a symlink on macOS, the
    kernel checks the real path).
    """
    allowed = " ".join(
        (
            *(f"(subpath {_quoted(path.resolve())})" for path in writable),
            *_WRITABLE_DEVICES,
        )
    )
    denied = "".join(
        f"(deny file-write* (subpath {_quoted(path.resolve())}))" for path in protected
    )
    return (
        "(version 1)(allow default)(deny file-write*)"
        f"(allow file-write* {allowed}){denied}"
    )


def bubblewrap_argv(bwrap: str, writable: Sequence[Path]) -> tuple[str, ...]:
    """The ``bwrap`` prefix: everything read-only but the ``writable`` directories."""
    binds = tuple(
        part
        for path in writable
        for part in ("--bind", str(path.resolve()), str(path.resolve()))
    )
    return (
        bwrap,
        "--die-with-parent",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        *binds,
        "--",
    )


def _candidate(
    writable: Sequence[Path], protected: Sequence[Path]
) -> tuple[str, ...] | None:
    if sys.platform == "darwin" and Path(SANDBOX_EXEC).exists():
        return (SANDBOX_EXEC, "-p", darwin_profile(writable, protected))
    bwrap = shutil.which("bwrap")
    if sys.platform.startswith("linux") and bwrap:
        return bubblewrap_argv(bwrap, writable)
    return None


def _applies(prefix: tuple[str, ...], cwd: Path) -> bool:
    """Whether ``prefix`` can confine a process here (probed with ``true``)."""
    true = shutil.which("true") or "/usr/bin/true"
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv
            [*prefix, true],
            cwd=cwd,
            capture_output=True,
            check=False,
            timeout=_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def confinement(
    writable: Sequence[Path], protected: Sequence[Path] = ()
) -> Confinement:
    """The confinement writing only under ``writable``, never under ``protected``.

    ``sandbox`` when the platform's sandbox applies here (probed from the first
    writable directory), else :data:`UNCONFINED` (``detect-only``).

    Raises:
        ValueError: ``writable`` is empty.
    """
    if not writable:
        raise ValueError("a confinement needs at least one writable directory")
    prefix = _candidate(writable, protected)
    if prefix is None or not _applies(prefix, writable[0]):
        return UNCONFINED
    return Confinement(isolation="sandbox", prefix=prefix)


def inherited_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The :data:`INHERITED_ENV` variables of ``source`` (the process's by default)."""
    variables = os.environ if source is None else source
    return {name: variables[name] for name in INHERITED_ENV if name in variables}


def private_environment(root: Path) -> dict[str, str]:
    """Home, temporary and XDG variables pointed into fresh directories of ``root``.

    The directories (:data:`PRIVATE_DIRS`) are created.
    """
    env: dict[str, str] = {}
    for name, sub in PRIVATE_DIRS.items():
        private = root / sub
        private.mkdir(parents=True, exist_ok=True)
        env[name] = str(private)
    return env


@dataclass(frozen=True)
class ConfinedRun:
    """A finished confined process: its isolation and what it printed."""

    isolation: Isolation
    returncode: int
    stdout: str
    stderr: str


def run_confined(  # noqa: PLR0913 - command, place, confinement and budget are distinct axes
    command: Sequence[str],
    *,
    writable: Sequence[Path],
    cwd: Path,
    env: Mapping[str, str] | None = None,
    protected: Sequence[Path] = (),
    timeout: float | None = None,
    confined: Confinement | None = None,
) -> ConfinedRun:
    """Run ``command`` writing only under ``writable``, in a filtered environment.

    The environment is :func:`inherited_environment` updated with ``env``;
    nothing else of the caller's environment is passed. ``confined`` is the
    confinement to apply, probed from ``writable`` and ``protected`` when
    omitted: the caller refuses a ``detect-only`` one beforehand if it must.

    Raises:
        subprocess.TimeoutExpired: The process outlived ``timeout``.
        OSError: The process could not start.
    """
    applied = confined or confinement(writable, protected)
    done = subprocess.run(  # noqa: S603 - caller's argv, no shell
        applied.wrap(command),
        cwd=cwd,
        env={**inherited_environment(), **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return ConfinedRun(
        isolation=applied.isolation,
        returncode=done.returncode,
        stdout=done.stdout,
        stderr=done.stderr,
    )
