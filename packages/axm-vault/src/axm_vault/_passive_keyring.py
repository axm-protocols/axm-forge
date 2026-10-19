"""Non-interactive Secret Service reads, retaining backend selection and order."""

from __future__ import annotations

from contextlib import closing
from importlib import import_module
from typing import cast

from keyring.backend import KeyringBackend
from keyring.backends import SecretService
from keyring.backends.chainer import ChainerBackend
from keyring.errors import InitError, KeyringLocked


def get_password(backend: KeyringBackend, service: str, username: str) -> str | None:
    """Read a credential without creating or unlocking Secret Service storage.

    Other backends retain their normal behavior. Chainers retain their ordered
    first-non-None lookup and propagate errors rather than bypassing a locked
    store to fetch a potentially stale credential from a lower-priority store.
    """
    if isinstance(backend, ChainerBackend):
        for child in backend.backends:
            password = get_password(child, service, username)
            if password is not None:
                return password
        return None
    if isinstance(backend, SecretService.Keyring):
        return _secret_service_password(backend, service, username)
    return backend.get_password(service, username)


def _secret_service_password(
    backend: SecretService.Keyring, service: str, username: str
) -> str | None:
    """Use only passive SecretStorage APIs, including after a lock race.

    SecretStorage is an optional, platform-specific dependency of keyring; load
    it only when the selected backend requires it. Never call keyring's
    get_preferred_collection/get_password: both can create or unlock storage.
    """
    storage = import_module("secretstorage")
    try:
        with closing(storage.dbus_init()) as connection:
            try:
                if hasattr(backend, "preferred_collection"):
                    collection = storage.Collection(
                        connection, backend.preferred_collection
                    )
                else:
                    collection = storage.get_collection_by_alias(connection, "default")
            except storage.exceptions.ItemNotFoundException:
                return None
            collection.ensure_not_locked()
            scheme = backend.schemes[backend.scheme]
            query = {scheme["service"]: service, scheme["username"]: username}
            for item in collection.search_items(query):
                item.ensure_not_locked()
                return cast(str, item.get_secret().decode("utf-8"))
    except storage.exceptions.LockedException:
        raise KeyringLocked("OS secret service is locked") from None
    except storage.exceptions.SecretStorageException:
        raise InitError("OS secret service is unavailable") from None
    return None
