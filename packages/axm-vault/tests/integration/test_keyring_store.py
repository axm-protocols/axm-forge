"""Integration tests for :class:`axm_vault.store.KeyringStore`.

These exercise the real ``keyring`` API surface against an in-memory backend
installed by the ``memory_keyring`` fixture — they never touch the OS Keychain
(AC4).
"""

from __future__ import annotations

import pytest

from axm_vault.store import KeyringStore


@pytest.mark.integration
def test_set_then_get(memory_keyring: object) -> None:
    """AC1, AC2, AC4: a value set under (group, name) is read back verbatim."""
    store = KeyringStore()

    store.set("linear", "api_key", "s3cr3t")

    assert store.get("linear", "api_key") == "s3cr3t"


@pytest.mark.integration
def test_get_absent_returns_none(memory_keyring: object) -> None:
    """AC2: reading an absent credential returns ``None`` rather than raising."""
    store = KeyringStore()

    assert store.get("linear", "api_key") is None


@pytest.mark.integration
def test_instance_namespacing_isolates(memory_keyring: object) -> None:
    """AC3, AC4: two instances of the same group/name do not collide."""
    store = KeyringStore()

    store.set("mail", "password", "pw-personal", instance="personal")
    store.set("mail", "password", "pw-work", instance="work")

    assert store.get("mail", "password", instance="personal") == "pw-personal"
    assert store.get("mail", "password", instance="work") == "pw-work"
    assert store.get("mail", "password") is None


@pytest.mark.integration
def test_delete_removes_credential(memory_keyring: object) -> None:
    """AC2, AC4: a deleted credential is no longer retrievable."""
    store = KeyringStore()
    store.set("linear", "api_key", "s3cr3t")

    store.delete("linear", "api_key")

    assert store.get("linear", "api_key") is None


@pytest.mark.integration
def test_delete_absent_is_noop(memory_keyring: object) -> None:
    """Deleting an absent credential is a no-op (the real Keychain raises).

    The macOS backend raises ``PasswordDeleteError`` (``Item not found``) on an
    absent key; :meth:`KeyringStore.delete` must swallow it so the documented
    no-op contract holds and rotation/cleanup callers never crash.
    """
    store = KeyringStore()

    store.delete("linear", "never_stored")

    assert store.get("linear", "never_stored") is None
