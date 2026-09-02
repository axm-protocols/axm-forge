from __future__ import annotations

import inspect
import shlex
from pathlib import Path

import axm_vault.cli
import pytest
from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec
from pytest import MonkeyPatch

from axm_doctor.orchestrate import missing_secrets


@pytest.mark.integration
def test_missing_secrets_preserves_mixed_requiredness(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC2: unresolved indispensable and optional specs remain distinguishable."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FIXTURE_REQUIRED_TOKEN", raising=False)
    monkeypatch.delenv("FIXTURE_OPTIONAL_TOKEN", raising=False)
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture.mixed",
                package="axm-fixture",
                title="Mixed",
                specs=(
                    CredentialSpec(
                        name="required_token",
                        env="FIXTURE_REQUIRED_TOKEN",
                        kind="token",
                        required=True,
                    ),
                    CredentialSpec(
                        name="optional_token",
                        env="FIXTURE_OPTIONAL_TOKEN",
                        kind="token",
                        required=False,
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()
    required_by_key = {(item.group, item.name): item.required for item in missing}

    assert required_by_key == {
        ("fixture.mixed", "required_token"): True,
        ("fixture.mixed", "optional_token"): False,
    }


@pytest.mark.integration
def test_missing_secrets_defaults_required_to_true(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC3: an omitted catalog required flag propagates its True default."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FIXTURE_DEFAULT_REQUIRED_TOKEN", raising=False)
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture.default",
                package="axm-fixture",
                title="Default",
                specs=(
                    CredentialSpec(
                        name="token",
                        env="FIXTURE_DEFAULT_REQUIRED_TOKEN",
                        kind="token",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()

    assert len(missing) == 1
    assert missing[0].required is True


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


@pytest.mark.integration
def test_missing_secrets_setup_hint_preserves_dotted_group(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC1: the setup hint keeps a dotted group as one positional argument."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FIXTURE_DOTTED_TOKEN", raising=False)
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture.dotted",
                package="axm-fixture",
                title="Dotted",
                specs=(
                    CredentialSpec(
                        name="api_token",
                        env="FIXTURE_DOTTED_TOKEN",
                        kind="token",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()

    assert len(missing) == 1
    assert missing[0].setup_hint == "axm-vault set fixture.dotted api_token"


@pytest.mark.integration
def test_missing_secrets_setup_hint_separates_plain_group_and_name(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC2: the setup hint separates a plain group and credential name."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FIXTURE_PLAIN_TOKEN", raising=False)
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture",
                package="axm-fixture",
                title="Plain",
                specs=(
                    CredentialSpec(
                        name="token",
                        env="FIXTURE_PLAIN_TOKEN",
                        kind="token",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()

    assert len(missing) == 1
    assert missing[0].setup_hint == "axm-vault set fixture token"


@pytest.mark.integration
def test_missing_secrets_setup_hints_bind_without_value_argument(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    memory_keyring: object,
) -> None:
    """AC3: every hint binds to the vault CLI without a value argument."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("FIXTURE_DOTTED_TOKEN", raising=False)
    monkeypatch.delenv("FIXTURE_PLAIN_TOKEN", raising=False)
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="fixture.dotted",
                package="axm-fixture",
                title="Dotted",
                specs=(
                    CredentialSpec(
                        name="api_token",
                        env="FIXTURE_DOTTED_TOKEN",
                        kind="token",
                    ),
                ),
            ),
            CredentialGroup(
                id="fixture",
                package="axm-fixture",
                title="Plain",
                specs=(
                    CredentialSpec(
                        name="token",
                        env="FIXTURE_PLAIN_TOKEN",
                        kind="token",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr("axm_doctor.orchestrate.load_catalog", lambda: catalog)

    missing = missing_secrets()

    assert len(missing) == 2
    for item in missing:
        tokens = shlex.split(item.setup_hint)
        assert len(tokens) == 4
        assert tokens[:2] == ["axm-vault", "set"]
        inspect.signature(axm_vault.cli.set).bind(*tokens[2:])
