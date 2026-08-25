"""Integration tests for the SECRET branch of :func:`axm_vault.setup.run_setup`.

These exercise ``run_setup`` end-to-end against the **real** ``axm_config``
(no stub): ``HOME`` is redirected to a tmp dir by the autouse ``_isolated_home``
fixture so ``~/.axm/<ns>.toml`` is hermetic, and the process keyring is the
in-memory backend installed by autouse ``_isolated_keyring``. The TTY guard and
:func:`getpass.getpass` prompt are mocked so the driver runs unattended.

This is the regression guard for AXM-2268: before the fix the SECRET branch
wrote a dotted sentinel key (``<name>.set``) that ``axm_config``'s ``_KEY_RE``
rejected with a ``ConfigError``. The write-only presence sentinel has since
been removed (it had zero readers and polluted ``config.toml``); the guard now
asserts the SECRET branch completes cleanly and writes *nothing* to
``axm_config`` — the secret goes to the keyring alone.
"""

from __future__ import annotations

import axm_config
import pytest

from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.setup import run_setup
from axm_vault.store import KeyringStore


def _secret_group() -> CredentialGroup:
    """A one-spec group whose single credential is SECRET."""
    return CredentialGroup(
        id="broker",
        package="axm-broker",
        title="Broker API",
        specs=(
            CredentialSpec(
                name="api_key",
                env="BROKER_API_KEY",
                kind="token",
                sensitivity=Sensitivity.SECRET,
            ),
        ),
    )


@pytest.mark.integration
def test_setup_secret_branch_real_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC4: the SECRET branch completes against the real axm_config.

    No ``ConfigError`` is raised, the secret value lands in the keyring, and
    ``axm_config`` receives *nothing* — neither the raw secret nor a presence
    marker (the write-only sentinel was removed).
    """
    import axm_vault.setup as setup_mod

    catalog = Catalog(groups=(_secret_group(),))
    monkeypatch.setattr(setup_mod, "load_catalog", lambda: catalog)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    # setup.py does `from getpass import getpass`, so the bound name lives on
    # the consuming module (patch there, not on the getpass module).
    monkeypatch.setattr(setup_mod, "getpass", lambda *a, **k: "s3cr3t-value")

    run_setup()

    # The secret value goes only to the keyring, never to axm_config.
    assert KeyringStore().get("broker", "api_key") == "s3cr3t-value"
    # No sentinel is written any more, and the raw secret never leaks either:
    # the SECRET branch touches axm_config not at all.
    assert axm_config.get("broker", "api_key_set") is None
    assert axm_config.get("broker", "api_key") is None
