"""Unit tests for :mod:`axm_vault.store` username composition.

These exercise the pure ``KeyringStore.username`` helper — no keyring I/O,
in-memory only (AC3).
"""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest
from keyring.errors import NoKeyringError

from axm_vault.store import (
    KeyringStore,
    KeyringUnavailableError,
    rotate_secret,
)


class _UnavailableKeyring(keyring.backend.KeyringBackend):
    """Backend simulating a headless host with no usable keyring."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]  # unstubbed keyring

    def get_password(self, service: str, username: str) -> str | None:
        raise NoKeyringError("No recommended backend was available")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise NoKeyringError("No recommended backend was available")

    def delete_password(self, service: str, username: str) -> None:
        raise NoKeyringError("No recommended backend was available")


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
def unavailable_keyring() -> Iterator[_UnavailableKeyring]:
    """Swap the process-wide keyring for one that always raises NoKeyringError."""
    backend = _UnavailableKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture
def mem_keyring() -> Iterator[_MemoryKeyring]:
    """Swap the process-wide keyring for an in-memory backend."""
    backend = _MemoryKeyring()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_username_without_instance() -> None:
    """AC3: instance segment is omitted cleanly when ``instance is None``."""
    assert KeyringStore.username("linear", "api_key") == "linear.api_key"


def test_username_with_instance() -> None:
    """AC3: instance segment is inserted between group and name when set."""
    assert (
        KeyringStore.username("mail", "password", instance="personal")
        == "mail.personal.password"
    )


def test_username_no_collision() -> None:
    """AC2: distinct (group, name, instance) tuples never collide on one username.

    With a naive ``\".\".join`` the tuples below all collapse to ``\"a.b.c\"``:
    a dot embedded in the group, a dot embedded in the name, and a genuine
    three-segment ``(group, instance, name)``. The hardened composition must
    escape/encode the segments so every distinct tuple maps to a distinct
    username.
    """
    dotted_group = KeyringStore.username("a.b", "c")
    dotted_name = KeyringStore.username("a", "b.c")
    with_instance = KeyringStore.username("a", "c", instance="b")
    usernames = {dotted_group, dotted_name, with_instance}
    assert len(usernames) == 3


def test_keyring_unavailable_raises_typed(
    unavailable_keyring: _UnavailableKeyring,
) -> None:
    """AC1: an unavailable keyring surfaces a typed KeyringUnavailableError.

    The error must be raised in place of a raw backend traceback, carry an
    actionable message, and never echo the secret value (never-leak invariant).
    """
    store = KeyringStore()
    secret = "s3cr3t-never-leak"
    with pytest.raises(KeyringUnavailableError) as exc_get:
        store.get("linear", "api_key")
    assert secret not in str(exc_get.value)

    with pytest.raises(KeyringUnavailableError) as exc_set:
        store.set("linear", "api_key", secret)
    assert secret not in str(exc_set.value)


def test_rotate_purges_old_prev(mem_keyring: _MemoryKeyring) -> None:
    """AC4: rotating twice retains exactly one ``.prev`` = the prior value.

    After two rotations only the immediately-previous secret lingers under
    ``{name}.prev`` — the first cycle's ``.prev`` is purged (one-cycle).
    """
    store = KeyringStore()
    store.set("svc", "token", "v0")

    rotate_secret("svc", "token", "v1")
    assert store.get("svc", "token") == "v1"
    assert store.get("svc", "token.prev") == "v0"

    rotate_secret("svc", "token", "v2")
    assert store.get("svc", "token") == "v2"
    # Only the immediately-previous value is retained, not an accumulation.
    assert store.get("svc", "token.prev") == "v1"
    assert store.get("svc", "token.prev.prev") is None
