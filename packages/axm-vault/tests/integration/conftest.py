"""Integration-level pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError


class _MemoryKeyring(KeyringBackend):
    """In-memory keyring backend for tests (never touches the OS Keychain).

    ``delete_password`` mirrors the real macOS Keychain backend by raising
    :class:`keyring.errors.PasswordDeleteError` on an absent key, so tests
    exercise the same contract production code faces.
    """

    priority = 1.0

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call] # keyring lacks stubs
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            raise PasswordDeleteError("not found")
        del self._store[(service, username)]


@pytest.fixture
def memory_keyring() -> Iterator[_MemoryKeyring]:
    """Install a fresh in-memory keyring backend, restoring the prior one."""
    previous = keyring.get_keyring()
    backend = _MemoryKeyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(previous)
