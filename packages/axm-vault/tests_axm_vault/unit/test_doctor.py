"""Unit tests for axm_vault.doctor — value-free provenance reporting."""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest

from axm_vault.catalog import Catalog
from axm_vault.doctor import doctor_data
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.store import KeyringStore


class _MemoryKeyring(keyring.backend.KeyringBackend):
    """In-memory keyring backend for unit tests (no OS Keychain)."""

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
    """Controllable in-memory instance source."""

    def __init__(self, names: tuple[str, ...], *, fail_on_list: bool = False) -> None:
        self._names = names
        self._fail_on_list = fail_on_list
        self.list_calls = 0

    def list_instances(self) -> tuple[str, ...]:
        self.list_calls += 1
        if self._fail_on_list:
            raise RuntimeError("instance source must not be enumerated")
        return self._names

    def declare(self, instance: str) -> None:
        self._names = (*self._names, instance)


def _multi_catalog(source: _Instances) -> Catalog:
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
        instances=source,
    )
    return Catalog(groups=(group,))


def _disable_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "axm_vault.doctor.Resolver.keyring_available", lambda _self: True
    )
    monkeypatch.setattr(
        "axm_vault.doctor.Resolver.probe",
        lambda _self, _layer, _spec, _group, _instance: False,
    )


@pytest.fixture
def mem_keyring() -> Iterator[_MemoryKeyring]:
    """Swap the process-wide keyring for an in-memory backend."""
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _secret_catalog() -> Catalog:
    """A catalog with one SECRET spec under group 'svc'."""
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
    )
    group = CredentialGroup(id="svc", package="pkg", title="Service", specs=(spec,))
    return Catalog(groups=(group,))


def test_doctor_reports_layer_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: a spec resolved from env reports layer 'env' and present True."""
    monkeypatch.setenv("SVC_TOKEN", "from-env")
    report = doctor_data(catalog=_secret_catalog())
    assert report["svc.token"] == {"layer": "env", "present": True}


def test_doctor_missing_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: nothing set -> layer 'missing', present False."""
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    import axm_config

    monkeypatch.setattr(axm_config, "get", lambda grp, name: None, raising=False)
    report = doctor_data(catalog=_secret_catalog())
    assert report["svc.token"] == {"layer": "missing", "present": False}


def test_doctor_never_returns_value(
    monkeypatch: pytest.MonkeyPatch, mem_keyring: _MemoryKeyring
) -> None:
    """AC2: a present SECRET value is never echoed anywhere in the output."""
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    import axm_config

    monkeypatch.setattr(axm_config, "get", lambda grp, name: None, raising=False)
    from axm_vault.store import KeyringStore

    KeyringStore().set("svc", "token", "PLAINTEXT")
    report = doctor_data(catalog=_secret_catalog())
    assert report["svc.token"] == {"layer": "keyring", "present": True}
    assert "PLAINTEXT" not in str(report)


def test_doctor_uses_canonical_key_for_each_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: each instance key uses the canonical escaped username composer."""
    source = _Instances(("perso", "a.b"))
    _disable_credentials(monkeypatch)

    report = doctor_data(catalog=_multi_catalog(source))

    expected = {
        KeyringStore.username("svc", "token", instance) for instance in ("perso", "a.b")
    }
    assert set(report) == expected


def test_doctor_explicit_instance_skips_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: an explicit instance is exclusive and bypasses enumeration."""
    source = _Instances((), fail_on_list=True)
    _disable_credentials(monkeypatch)

    report = doctor_data(catalog=_multi_catalog(source), instance="pro")

    assert report == {
        KeyringStore.username("svc", "token", "pro"): {
            "layer": "missing",
            "present": False,
        }
    }
    assert source.list_calls == 0
