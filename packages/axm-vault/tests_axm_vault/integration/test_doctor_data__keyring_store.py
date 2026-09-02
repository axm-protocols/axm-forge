"""Integration tests for per-instance doctor keyring provenance."""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest

from axm_vault.catalog import Catalog
from axm_vault.doctor import doctor_data
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.store import KeyringStore


class _MemoryKeyring(keyring.backend.KeyringBackend):
    """In-memory backend exercising the public keyring store boundary."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # unstubbed keyring
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


class _Instances:
    """In-memory source for declared instance identities."""

    def __init__(self, names: tuple[str, ...]) -> None:
        self._names = names

    def list_instances(self) -> tuple[str, ...]:
        return self._names

    def declare(self, instance: str) -> None:
        self._names = (*self._names, instance)


@pytest.fixture
def mem_keyring() -> Iterator[_MemoryKeyring]:
    """Install an isolated backend for the integration boundary."""
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _multi_catalog() -> Catalog:
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
    )
    group = CredentialGroup(
        id="svc",
        package="pkg",
        title="Service",
        specs=(spec,),
        multi=True,
        instances=_Instances(("perso", "pro")),
    )
    return Catalog(groups=(group,))


@pytest.mark.integration
def test_doctor_reports_each_declared_instance(
    monkeypatch: pytest.MonkeyPatch, mem_keyring: _MemoryKeyring
) -> None:
    """AC1: two instances yield distinct present and missing provenance rows."""
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    import axm_config

    monkeypatch.setattr(axm_config, "get", lambda _group, _name: None)
    KeyringStore().set("svc", "token", "provisioned", instance="perso")

    report = doctor_data(catalog=_multi_catalog())

    perso = KeyringStore.username("svc", "token", "perso")
    pro = KeyringStore.username("svc", "token", "pro")
    assert report == {
        perso: {"layer": "keyring", "present": True},
        pro: {"layer": "missing", "present": False},
    }
