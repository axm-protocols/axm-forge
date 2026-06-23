from __future__ import annotations

from pathlib import Path

import pytest
from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec
from pytest import MonkeyPatch

from axm_doctor.orchestrate import missing_secrets


@pytest.mark.integration
def test_missing_secrets_real_vault_provenance(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC1: over real vault provenance, a set spec is absent and an unset one present.

    Exercises the real :func:`axm_vault.doctor.doctor_data` resolver chain
    against a fixture catalog: the env layer supplies ``set.token`` (so it is
    NOT missing) while ``unset.token`` resolves nowhere (so it IS missing).
    HOME is redirected to ``tmp_path`` and the keyring is in-memory so the file
    and keyring layers stay clean.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("FIXTURE_SET_TOKEN", "present-via-env")
    monkeypatch.delenv("FIXTURE_UNSET_TOKEN", raising=False)

    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture.set",
                package="axm-fixture",
                title="Set",
                specs=(
                    CredentialSpec(name="token", env="FIXTURE_SET_TOKEN", kind="token"),
                ),
            ),
            CredentialGroup(
                id="fixture.unset",
                package="axm-fixture",
                title="Unset",
                specs=(
                    CredentialSpec(
                        name="token", env="FIXTURE_UNSET_TOKEN", kind="token"
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()
    keys = {(m.group, m.name) for m in missing}

    assert ("fixture.unset", "token") in keys
    assert ("fixture.set", "token") not in keys
