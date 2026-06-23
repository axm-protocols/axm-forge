"""Interactive credential setup — the ``axm-vault setup`` driver.

:func:`run_setup` walks the discovered credential catalog and, for every
spec, prompts the operator for a value and routes it to its store by
sensitivity: SECRET values go to the OS keyring (with a value-free
presence sentinel in :mod:`axm_config`), CONFIG values go to ``axm-config``.
NONSENSITIVE credentials are environment-only and are never prompted nor
stored — storing them would create a second, stale source of truth.

The driver is a genuine *process-lifecycle* command (it reads from a TTY and
blocks on operator input), which is why it lives as a plain function behind
the cyclopts CLI rather than as an :class:`~axm.tools.base.AXMTool`. It
refuses to run without a TTY (no silent, non-interactive credential writes)
and is idempotent: a blank answer keeps any existing value untouched, so a
re-run only fills in what is still missing.
"""

from __future__ import annotations

import sys
from getpass import getpass
from typing import TYPE_CHECKING

import axm_config

from axm_vault.catalog import load_catalog
from axm_vault.models import Layer, Sensitivity
from axm_vault.resolver import resolver
from axm_vault.store import KeyringStore

if TYPE_CHECKING:
    from axm_vault.models import CredentialGroup, CredentialSpec

__all__ = ["run_setup"]

_SENTINEL_SUFFIX = "_set"
"""Config key suffix marking a SECRET as present without storing its value.

Underscore-joined (not dotted) so the derived sentinel key ``<name>_set``
stays within axm-config's key charset (``^[A-Za-z0-9_]+$``); a dotted suffix
would be rejected by ``axm_config.set_`` and break the SECRET branch.
"""

# Layers a setup probe consults for an existing value. ``default``/``prompt``
# are excluded: a spec default is not a stored value, and prompting here would
# recurse into setup's own prompt.
_PRESENCE_LAYERS: tuple[Layer, ...] = ("env", "file", "keyring")


def run_setup(only: str | None = None) -> None:
    """Prompt for and store every storable credential in the catalog.

    Args:
        only: When given, restrict setup to the single ``group.name`` (or a
            bare ``name``) matching this string; otherwise cover every spec.

    The function refuses to run without an interactive TTY (writes
    :class:`SystemExit` ``1`` to stderr). NONSENSITIVE specs are skipped
    (environment-only); SECRET specs are read with :func:`getpass.getpass`
    and CONFIG specs with :func:`input`. A blank answer keeps the existing
    value, making the driver idempotent across re-runs.
    """
    if not sys.stdin.isatty():
        print(
            "axm-vault setup requires an interactive terminal (TTY).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    keyring = KeyringStore()
    for group in load_catalog().groups():
        for spec in group.specs:
            if only is not None and only not in (f"{group.id}.{spec.name}", spec.name):
                continue
            _setup_spec(keyring, group, spec)


def _setup_spec(
    keyring: KeyringStore, group: CredentialGroup, spec: CredentialSpec
) -> None:
    """Prompt for one spec and route the answer to its store by sensitivity.

    NONSENSITIVE specs are skipped outright (env-only). A blank answer is a
    no-op, preserving any value already present (idempotence, AC2).
    """
    if spec.sensitivity is Sensitivity.NONSENSITIVE:
        return
    present = _is_present(group, spec)
    answer = _prompt(group, spec, present=present)
    if not answer:
        return
    if spec.sensitivity is Sensitivity.SECRET:
        keyring.set(group.id, spec.name, answer)
        axm_config.set_(group.id, spec.name + _SENTINEL_SUFFIX, True)
    else:
        axm_config.set_(group.id, spec.name, answer)


def _is_present(group: CredentialGroup, spec: CredentialSpec) -> bool:
    """Report whether ``group.spec`` already resolves from a stored layer."""
    return any(resolver.probe(layer, spec, group) for layer in _PRESENCE_LAYERS)


def _prompt(group: CredentialGroup, spec: CredentialSpec, *, present: bool) -> str:
    """Ask the operator for ``group.spec``; SECRET uses :func:`getpass`.

    The prompt advertises ``[keep]`` when a value already exists so a blank
    answer is understood as “keep the current value”.
    """
    label = spec.prompt or f"{group.id}.{spec.name}"
    hint = " [keep]" if present else ""
    text = f"{label}{hint}: "
    if spec.sensitivity is Sensitivity.SECRET:
        return getpass(text)
    return input(text)
