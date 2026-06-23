"""Integration tests for axm_vault.tools — real keyring boundary."""

from __future__ import annotations

import pytest

from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.store import KeyringStore
from axm_vault.tools import VaultSetTool


def _secret_catalog() -> Catalog:
    group = CredentialGroup(
        id="svc",
        package="pkg",
        title="Service",
        specs=(
            CredentialSpec(
                name="token",
                env="SVC_TOKEN",
                kind="token",
                sensitivity=Sensitivity.SECRET,
                required=False,
            ),
        ),
    )
    return Catalog(groups=(group,))


@pytest.mark.integration
def test_vault_set_secret_to_keyring(
    monkeypatch: pytest.MonkeyPatch, memory_keyring: object
) -> None:
    """AC4: a SECRET value is stored in the keyring; data reports 'stored', no echo."""
    import axm_vault.tools as tools_mod

    monkeypatch.setattr(tools_mod, "load_catalog", lambda: _secret_catalog())
    result = VaultSetTool().execute(group="svc", name="token", value="s3cret")
    assert result.success is True
    assert "stored" in result.data
    assert KeyringStore().get("svc", "token") == "s3cret"
    assert "s3cret" not in str(result.data)
