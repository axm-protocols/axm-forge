"""``axm-vault`` command-line interface (cyclopts).

The CLI is a thin shell: it owns argument parsing and human-facing output,
but delegates every operation to the central functions / tools so no
business logic is duplicated across the CLI / MCP boundary. ``setup`` is the
only genuine process-lifecycle command (interactive prompts); ``set``/``doctor``
are backed by the :class:`~axm.tools.base.AXMTool` implementations, and
``get``/``rotate``/``path`` call the resolver, store and config primitives
directly. There is deliberately **no** ``import`` command — a bulk importer is
deferred.
"""

from __future__ import annotations

import getpass
import sys

import axm_config
import cyclopts

from axm_vault.catalog import load_catalog
from axm_vault.doctor import doctor_data
from axm_vault.models import Sensitivity
from axm_vault.resolver import MissingCredentialError, resolver
from axm_vault.secrets import MASK
from axm_vault.setup import run_setup
from axm_vault.store import KeyringStore, rotate_secret
from axm_vault.tools import VaultSetTool

_RESOLVE_ERRORS = (KeyError, MissingCredentialError)


def _die(exc: Exception) -> None:
    """Print ``exc`` to stderr and exit 1 (the CLI error-path convention)."""
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)


__all__ = ["app", "main"]

app = cyclopts.App(
    name="axm-vault",
    help="Catalog-resolver secrets manager (keyring + SecretStr) for AXM.",
)


@app.command
def setup(only: str | None = None) -> None:
    """Interactively prompt for and store every storable credential.

    Args:
        only: Restrict setup to a single ``group.name`` (or bare ``name``).
    """
    run_setup(only)


@app.command
def get(group: str, name: str, *, reveal: bool = False) -> None:
    """Resolve ``group.name`` and print it, masking SECRET values.

    Args:
        group: Credential group id.
        name: Credential name within the group.
        reveal: Print the plaintext even for SECRET specs (a deliberate
            opt-in reveal; no audit trail is emitted).
    """
    try:
        grp = load_catalog().group(group)
        resolved = resolver.resolve(grp, name)
    except _RESOLVE_ERRORS as exc:
        _die(exc)
        return
    secret = resolved.spec.sensitivity is Sensitivity.SECRET
    print(MASK if secret and not reveal else (resolved.value or ""))


@app.command
def set(group: str, name: str, value: str | None = None) -> None:  # CLI verb
    """Store ``group.name`` in its backend (keyring for SECRET, config else).

    Args:
        group: Credential group id.
        name: Credential name within the group.
        value: The value to store (never echoed back). Omit it to be prompted
            for the secret via a hidden :func:`getpass.getpass` input — the
            plaintext then never appears on the process argv.
    """
    if value is None:
        value = getpass.getpass(f"Secret for {group}.{name}: ")
    result = VaultSetTool().execute(group=group, name=name, value=value)
    if not result.success:
        print(result.error, file=sys.stderr)
        raise SystemExit(1)
    print(result.data["stored"])


@app.command
def rotate(
    group: str, name: str, value: str | None = None, instance: str | None = None
) -> None:
    """Rotate a SECRET to ``value``, retaining the previous one for one cycle.

    The spec is resolved through the catalog first and MUST be
    :data:`~axm_vault.models.Sensitivity.SECRET`: only SECRET specs live in the
    keyring, so rotating a CONFIG/NONSENSITIVE spec (or an unknown name) would
    write an orphan into the keyring that ``get`` never reads — a silent no-op
    reported as success. Routing through the catalog turns that into an
    up-front error, mirroring ``set``'s sensitivity check.

    Args:
        group: Credential group id.
        name: Credential name within the group.
        value: The new secret value (never echoed back). Omit it to be prompted
            via a hidden :func:`getpass.getpass` input, keeping the plaintext
            off the process argv.
        instance: Optional multi-instance segment.
    """
    if value is None:
        value = getpass.getpass(f"New secret for {group}.{name}: ")
    try:
        spec = load_catalog().group(group).spec(name)
        if spec.sensitivity is not Sensitivity.SECRET:
            msg = (
                f"cannot rotate {group}.{name}: only SECRET credentials live "
                f"in the keyring (this spec is {spec.sensitivity.value.upper()})"
            )
            raise ValueError(msg)
        rotate_secret(group, name, value, instance)
    except Exception as exc:  # noqa: BLE001 # CLI boundary: any error -> exit 1
        _die(exc)
        return
    print(f"rotated keyring:{group}.{name}")


@app.command
def delete(group: str, name: str, instance: str | None = None) -> None:
    """Remove ``group.name`` from the keyring (a safe no-op if already absent).

    The spec is resolved through the catalog first (an unknown ``group.name``
    is an up-front error), then the credential is deleted from the keyring. The
    delete is idempotent: removing an already-absent secret succeeds silently.

    Args:
        group: Credential group id.
        name: Credential name within the group.
        instance: Optional multi-instance segment.
    """
    try:
        spec = load_catalog().group(group).spec(name)
        KeyringStore().delete(group, spec.name, instance)
    except Exception as exc:  # noqa: BLE001 # CLI boundary: any error -> exit 1
        _die(exc)
        return
    print(f"deleted keyring:{group}.{name}")


@app.command
def doctor(package: str | None = None, instance: str | None = None) -> None:
    """Print value-free provenance for every credential in the catalog.

    Args:
        package: Restrict the report to one contributing package.
        instance: Optional multi-instance segment.
    """
    for key, entry in doctor_data(package, instance=instance).items():
        present = "present" if entry["present"] else "-"
        line = f"{key}\t{entry['layer']}\t{present}"
        if entry.get("keyring") == "unavailable":
            line += "\tkeyring:unavailable"
        print(line)


@app.command
def path() -> None:
    """Print the resolved ``~/.axm`` home directory used for file-backed config."""
    print(axm_config.axm_home())


def main() -> None:
    """Console-script entry point for ``axm-vault``."""
    app()
