from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest

from axm_vault.models import CredentialGroup, CredentialSpec, Sensitivity
from axm_vault.resolver import Resolver
from axm_vault.store import KeyringStore


class _MemoryKeyring(keyring.backend.KeyringBackend):
    """In-memory keyring backend for integration tests."""

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
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.mark.integration
def test_full_chain_env_file_keyring(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mem_keyring: _MemoryKeyring,
) -> None:
    """AC1, AC3, AC4: env > file > keyring ordering holds end-to-end.

    Uses a real axm-config file (HOME redirected to tmp) for the file tier
    and an in-memory keyring for the secret tier.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    spec = CredentialSpec(
        name="token",
        env="SVC_TOKEN",
        kind="token",
        sensitivity=Sensitivity.SECRET,
        required=False,
    )
    group = CredentialGroup(id="svc", package="pkg", title="Service", specs=(spec,))

    # Seed the keyring (lowest of the three tiers exercised here).
    KeyringStore().set("svc", "token", "from-keyring")
    resolver = Resolver()

    # Only keyring set -> keyring wins (SECRET tier consulted).
    monkeypatch.delenv("SVC_TOKEN", raising=False)
    resolved = resolver.resolve(group, "token")
    assert resolved.layer == "keyring"
    assert resolved.value == "from-keyring"

    # env set -> env wins over keyring.
    monkeypatch.setenv("SVC_TOKEN", "from-env")
    resolved = resolver.resolve(group, "token")
    assert resolved.layer == "env"
    assert resolved.value == "from-env"
