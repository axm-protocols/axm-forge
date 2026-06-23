"""``axm-config`` command-line interface.

Process-lifecycle surface only: every command body delegates to the central
requete->reponse layer (``get``/``set_``/``axm_home``/``config_doctor_data``).
No resolution or persistence logic lives here (AXMTool-first convention).
"""

from __future__ import annotations

import sys
from typing import Annotated, NoReturn

import cyclopts

from axm_config.doctor import config_doctor_data
from axm_config.home import axm_home
from axm_config.resolver import ConfigError, delete, get, set_

__all__ = ["app"]

app = cyclopts.App(
    name="axm-config",
    help="Non-sensitive runtime config under ~/.axm (env>file>default).",
)


def _die(exc: OSError | ConfigError) -> NoReturn:
    """Report an operational failure on stderr and exit ``1`` (no traceback).

    The CLI is the process-lifecycle surface: an ``~/.axm`` that cannot be
    created or written (``OSError``/``PermissionError``), or a config that
    cannot be resolved (:class:`ConfigError`), surfaces as a clean one-line
    error rather than a raw Python stack trace.
    """
    print(f"error: {exc}", file=sys.stderr)  # noqa: T201 - CLI error output
    raise SystemExit(1)


@app.command(name="get")
def _get_cmd(
    namespace: Annotated[str, cyclopts.Parameter(help="Config namespace.")],
    key: Annotated[str, cyclopts.Parameter(help="Config key.")],
) -> None:
    """Print the resolved value for ``key`` in ``namespace`` (env>file>default)."""
    try:
        value = get(namespace, key)
    except (OSError, ConfigError) as exc:
        _die(exc)
    print(value)  # noqa: T201 - CLI output


@app.command(name="set")
def _set_cmd(
    namespace: Annotated[str, cyclopts.Parameter(help="Config namespace.")],
    key: Annotated[str, cyclopts.Parameter(help="Config key.")],
    value: Annotated[str, cyclopts.Parameter(help="Value to persist.")],
) -> None:
    """Persist ``key`` = ``value`` in the ``[namespace]`` section of config.toml."""
    try:
        set_(namespace, key, value)
    except (OSError, ConfigError) as exc:
        _die(exc)


@app.command(name="delete")
def _delete_cmd(
    namespace: Annotated[str, cyclopts.Parameter(help="Config namespace.")],
    key: Annotated[str, cyclopts.Parameter(help="Config key.")],
) -> None:
    """Remove ``key`` from the ``[namespace]`` section (no-op if absent)."""
    try:
        delete(namespace, key)
    except (OSError, ConfigError) as exc:
        _die(exc)


@app.command(name="path")
def _path_cmd() -> None:
    """Print the resolved ``~/.axm`` home directory."""
    try:
        home = axm_home()
    except OSError as exc:
        _die(exc)
    print(home)  # noqa: T201 - CLI output


@app.command(name="doctor")
def _doctor_cmd(
    namespace: Annotated[
        str | None,
        cyclopts.Parameter(help="Namespace to inspect; all known if omitted."),
    ] = None,
) -> None:
    """Print per-key provenance (``env``/``file``/``default``), read-only."""
    try:
        report = config_doctor_data(namespace)
    except (OSError, ConfigError) as exc:
        _die(exc)
    for dotted_key, info in report.items():
        print(f"{dotted_key}: {info['layer']}")  # noqa: T201 - CLI output
