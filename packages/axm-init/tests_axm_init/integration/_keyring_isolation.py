"""Hermetic credential fixtures for integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest
from axm_vault import KeyringStore
from keyring.backend import KeyringBackend

from axm_init.credentials_catalog import pypi_credentials

SENTINEL_PYPI_TOKEN = "pypi-AgEIcHlwaS5vcmc-SENTINEL"


class MemoryKeyring(KeyringBackend):
    """Process-local keyring backend that never touches the operating system."""

    priority = 1

    def __init__(self) -> None:
        self._passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        """Return the stored password, if any."""
        return self._passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        """Store a password in process memory."""
        self._passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        """Delete a password without consulting an external backend."""
        self._passwords.pop((service, username), None)


@pytest.fixture(autouse=True)
def isolated_keyring() -> Iterator[MemoryKeyring]:
    """Install a fresh memory keyring for one integration test."""
    previous_backend = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(previous_backend)


@pytest.fixture(autouse=True)
def isolated_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Point home-directory resolution at a fresh pytest temporary directory."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    yield home


@pytest.fixture()
def seeded_pypi_keyring(
    isolated_keyring: MemoryKeyring,
    monkeypatch: pytest.MonkeyPatch,
) -> MemoryKeyring:
    """Seed the PyPI sentinel into the active memory keyring."""
    monkeypatch.delenv("PYPI_API_TOKEN", raising=False)
    group = pypi_credentials()[0]
    spec = group.specs[0]
    KeyringStore().set(group.id, spec.name, SENTINEL_PYPI_TOKEN)
    return isolated_keyring
