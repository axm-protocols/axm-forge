"""Unit tests for axm_vault.tools — vault_doctor / vault_set MCP tools."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import keyring
import pytest

from axm_vault.catalog import Catalog
from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.tools import VaultDoctorTool, VaultSetTool


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


@pytest.fixture
def mem_keyring() -> Iterator[_MemoryKeyring]:
    """Swap the process-wide keyring for an in-memory backend."""
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _secret_group() -> CredentialGroup:
    return CredentialGroup(
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


def _catalog(*groups: CredentialGroup) -> Catalog:
    return Catalog(groups=tuple(groups))


def _patch_catalog(monkeypatch: pytest.MonkeyPatch, catalog: Catalog) -> None:
    """Force load_catalog() to return our fixture catalog on every call site.

    ``vault_set`` reads the catalog in ``axm_vault.tools``; ``vault_doctor``
    delegates to ``doctor_data`` which reads it in ``axm_vault.doctor``.
    """
    import axm_vault.doctor as doctor_mod
    import axm_vault.tools as tools_mod

    monkeypatch.setattr(tools_mod, "load_catalog", lambda: catalog)
    monkeypatch.setattr(doctor_mod, "load_catalog", lambda: catalog)


def test_vault_doctor_tool_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: VaultDoctorTool returns success True with provenance data."""
    monkeypatch.setenv("SVC_TOKEN", "from-env")
    _patch_catalog(monkeypatch, _catalog(_secret_group()))
    result = VaultDoctorTool().execute()
    assert result.success is True
    assert result.data["svc.token"] == {"layer": "env", "present": True}


def test_vault_doctor_serialized_never_leaks(
    monkeypatch: pytest.MonkeyPatch, mem_keyring: _MemoryKeyring
) -> None:
    """AC5: the serialized vault_doctor ToolResult contains the plaintext NOWHERE."""
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    import axm_config

    monkeypatch.setattr(axm_config, "get", lambda grp, name: None, raising=False)
    from axm_vault.store import KeyringStore

    KeyringStore().set("svc", "token", "PLAINTEXT")
    _patch_catalog(monkeypatch, _catalog(_secret_group()))
    result = VaultDoctorTool().execute()
    serialized = str(dataclasses.asdict(result))
    assert "PLAINTEXT" not in serialized
    assert result.data["svc.token"] == {"layer": "keyring", "present": True}


def test_vault_set_nonsensitive_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC4: a NONSENSITIVE spec is env-only -> rejected, never stored."""
    _patch_catalog(monkeypatch, _catalog(_nonsensitive_group()))
    result = VaultSetTool().execute(group="svc", name="account_id", value="123")
    assert result.success is False
    assert result.error is not None
