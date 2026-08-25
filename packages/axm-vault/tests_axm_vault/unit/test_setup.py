"""Unit tests for axm_vault.setup — interactive run_setup driver."""

from __future__ import annotations

import pytest

from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity


def _nonsensitive_group() -> CredentialGroup:
    return CredentialGroup(
        id="svc",
        package="pkg",
        title="Service",
        specs=(
            CredentialSpec(
                name="account_id",
                env="SVC_ACCOUNT_ID",
                kind="id",
                sensitivity=Sensitivity.NONSENSITIVE,
                required=False,
            ),
        ),
    )


def _patch_catalog(monkeypatch: pytest.MonkeyPatch, catalog: Catalog) -> None:
    """Force run_setup's catalog discovery to return our fixture catalog."""
    import axm_vault.setup as setup_mod

    monkeypatch.setattr(setup_mod, "load_catalog", lambda: catalog)


def test_setup_refuses_non_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: run_setup refuses to run without a TTY (SystemExit(1))."""
    from axm_vault.setup import run_setup

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit) as excinfo:
        run_setup()
    assert excinfo.value.code == 1


def test_setup_skips_nonsensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: NONSENSITIVE specs are env-only — never written to any store."""
    import axm_config

    from axm_vault.setup import run_setup
    from axm_vault.store import KeyringStore

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    _patch_catalog(monkeypatch, Catalog(groups=(_nonsensitive_group(),)))

    keyring_writes: list[tuple[str, str, str]] = []
    config_writes: list[tuple[str, str, object]] = []
    monkeypatch.setattr(
        KeyringStore,
        "set",
        lambda self, g, n, v, instance=None: keyring_writes.append((g, n, v)),
    )
    monkeypatch.setattr(
        axm_config,
        "set_",
        lambda ns, key, value: config_writes.append((ns, key, value)),
        raising=False,
    )
    # Any prompt invocation on a NONSENSITIVE spec would itself be a bug.
    monkeypatch.setattr(
        "builtins.input", lambda *a, **k: pytest.fail("prompted NONSENSITIVE")
    )
    monkeypatch.setattr(
        "getpass.getpass", lambda *a, **k: pytest.fail("prompted NONSENSITIVE")
    )

    run_setup()

    assert keyring_writes == []
    assert config_writes == []
