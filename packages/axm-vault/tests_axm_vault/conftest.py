"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

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


@pytest.fixture(autouse=True)
def _isolated_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Redirect ``HOME`` so ``~/.axm`` resolves inside a tmp dir.

    ``axm_config.axm_home`` (consulted by the file tier) calls ``Path.home()``
    live on every call, so redirecting ``HOME`` keeps the file tier hermetic.
    Any leaked ``AXM_*`` provenance variable is also cleared so layer probes
    start from a clean slate regardless of test ordering. A *dedicated* tmp dir
    is used (not the function-scoped ``tmp_path``) so the eagerly-created
    ``~/.axm`` never pollutes a test's own ``tmp_path``; tests that redirect
    ``HOME`` to their own ``tmp_path`` simply override this fixture.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    for name in [key for key in os.environ if key.startswith("AXM_")]:
        monkeypatch.delenv(name, raising=False)
    yield home


@pytest.fixture(autouse=True)
def _isolated_keyring() -> Iterator[_MemoryKeyring]:
    """Globally swap the process keyring for an in-memory backend.

    Autouse so *every* test — including those that probe the keyring layer
    indirectly (``doctor_data``, ``run_setup``) without requesting a named
    fixture — reads and writes an in-memory store, never the real OS Keychain.
    The prior backend is restored on teardown. Tests that still request the
    named ``memory_keyring`` / ``mem_keyring`` fixtures override this one for
    their scope and restore back to it, so they keep working unchanged.
    """
    previous = keyring.get_keyring()
    backend = _MemoryKeyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(previous)
