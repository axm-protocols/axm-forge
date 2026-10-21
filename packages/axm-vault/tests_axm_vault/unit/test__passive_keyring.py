"""Passive reads must never invoke Secret Service create/unlock prompts."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.backends import SecretService
from keyring.backends.chainer import ChainerBackend
from keyring.errors import KeyringLocked

from axm_vault.store import SERVICE, KeyringStore, KeyringUnavailableError


class _StorageError(Exception):
    pass


class _MissingError(_StorageError):
    pass


class _LockedError(_StorageError):
    pass


@pytest.fixture
def secret_service(monkeypatch):
    """Fake only the D-Bus boundary; exercise the selected real backend class."""
    connection = Mock(spec=["close"])
    item = Mock(spec=["ensure_not_locked", "get_secret"])
    item.get_secret.return_value = b"saved-secret"
    collection = Mock(spec=["ensure_not_locked", "search_items"])
    collection.search_items.return_value = [item]
    storage = SimpleNamespace(
        dbus_init=Mock(return_value=connection),
        Collection=Mock(return_value=collection),
        get_collection_by_alias=Mock(return_value=collection),
        get_default_collection=Mock(side_effect=AssertionError("created collection")),
        exceptions=SimpleNamespace(
            ItemNotFoundException=_MissingError,
            LockedException=_LockedError,
            SecretStorageException=_StorageError,
        ),
    )
    monkeypatch.setitem(sys.modules, "secretstorage", storage)
    monkeypatch.setattr(SecretService, "secretstorage", storage, raising=False)
    monkeypatch.setattr(SecretService, "exceptions", storage.exceptions, raising=False)

    class SelectedBackend(SecretService.Keyring):
        priority = 5

    backend = SelectedBackend()  # type: ignore[no-untyped-call]
    keyring.set_keyring(backend)
    return SimpleNamespace(
        backend=backend,
        storage=storage,
        connection=connection,
        collection=collection,
        item=item,
    )


def test_missing_default_is_absent_without_creating(secret_service):
    secret_service.storage.get_collection_by_alias.side_effect = _MissingError()
    assert KeyringStore().get("weather", "arome_pi") is None
    secret_service.storage.get_default_collection.assert_not_called()
    secret_service.storage.Collection.assert_not_called()
    secret_service.connection.close.assert_called_once()


@pytest.mark.parametrize("scheme", ["default", "KeePassXC"])
def test_unlocked_secret_preserves_backend_query_scheme(secret_service, scheme):
    secret_service.backend.scheme = scheme
    assert KeyringStore().get("weather", "arome_pi") == "saved-secret"
    fields = secret_service.backend.schemes[scheme]
    secret_service.collection.search_items.assert_called_once_with(
        {
            fields["service"]: SERVICE,
            fields["username"]: "weather.arome_pi",
        }
    )
    secret_service.storage.get_collection_by_alias.assert_called_once_with(
        secret_service.connection,
        "default",
    )
    secret_service.connection.close.assert_called_once()


def test_preferred_collection_does_not_fall_back_to_default(secret_service):
    secret_service.backend.preferred_collection = "/org/freedesktop/secrets/custom"
    assert KeyringStore().get("weather", "arome_pi") == "saved-secret"
    secret_service.storage.Collection.assert_called_once_with(
        secret_service.connection,
        "/org/freedesktop/secrets/custom",
    )
    secret_service.storage.get_collection_by_alias.assert_not_called()


def test_missing_preferred_collection_is_absent(secret_service):
    secret_service.backend.preferred_collection = "/missing"
    secret_service.storage.Collection.side_effect = _MissingError()
    assert KeyringStore().get("weather", "arome_pi") is None
    secret_service.storage.get_collection_by_alias.assert_not_called()


@pytest.mark.parametrize("failure_at", ["collection", "item", "get_secret"])
def test_locked_or_lock_race_is_typed_without_unlocking(secret_service, failure_at):
    target = {
        "collection": secret_service.collection.ensure_not_locked,
        "item": secret_service.item.ensure_not_locked,
        "get_secret": secret_service.item.get_secret,
    }[failure_at]
    target.side_effect = _LockedError("never-echo-this-secret")
    with pytest.raises(KeyringUnavailableError) as error:
        KeyringStore().get("weather", "arome_pi")
    assert "never-echo-this-secret" not in str(error.value)
    secret_service.connection.close.assert_called_once()


def test_service_failure_is_typed_and_redacted(secret_service):
    secret_service.storage.dbus_init.side_effect = _StorageError("private-payload")
    with pytest.raises(KeyringUnavailableError) as error:
        KeyringStore().get("weather", "arome_pi")
    assert "private-payload" not in str(error.value)


def test_missing_item_returns_none(secret_service):
    secret_service.collection.search_items.return_value = []
    assert KeyringStore().get("weather", "arome_pi") is None


def test_explicit_write_retains_backend_prompt_path(secret_service, monkeypatch):
    write = Mock()
    monkeypatch.setattr(secret_service.backend, "set_password", write)
    KeyringStore().set("weather", "arome_pi", "new-secret")
    write.assert_called_once_with(SERVICE, "weather.arome_pi", "new-secret")


def test_cancelled_write_is_typed(secret_service, monkeypatch):
    monkeypatch.setattr(
        secret_service.backend,
        "set_password",
        Mock(side_effect=KeyringLocked("cancelled private-payload")),
    )
    with pytest.raises(KeyringUnavailableError) as error:
        KeyringStore().set("weather", "arome_pi", "new-secret")
    assert "private-payload" not in str(error.value)


class _Chain(ChainerBackend):
    priority = 10
    backends: tuple[KeyringBackend, ...] = ()


def test_chainer_continues_after_missing_and_stops_on_empty_string(secret_service):
    secret_service.storage.get_collection_by_alias.side_effect = _MissingError()
    empty = Mock()
    empty.get_password.return_value = ""
    later = Mock()
    chain = _Chain()  # type: ignore[no-untyped-call]
    chain.backends = (secret_service.backend, empty, later)
    keyring.set_keyring(chain)
    assert KeyringStore().get("weather", "arome_pi") == ""
    empty.get_password.assert_called_once_with(SERVICE, "weather.arome_pi")
    later.get_password.assert_not_called()


def test_chainer_preserves_locked_failure_without_fallback(secret_service):
    secret_service.collection.ensure_not_locked.side_effect = _LockedError()
    later = Mock()
    chain = _Chain()  # type: ignore[no-untyped-call]
    chain.backends = (secret_service.backend, later)
    keyring.set_keyring(chain)
    with pytest.raises(KeyringUnavailableError):
        KeyringStore().get("weather", "arome_pi")
    later.get_password.assert_not_called()
