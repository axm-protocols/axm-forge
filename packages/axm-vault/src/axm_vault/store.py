"""Keyring-backed credential store for AXM.

:class:`KeyringStore` is a thin, stateless wrapper over the OS keyring
(`keyring <https://github.com/jaraco/keyring>`_). Secrets are stored under a
single fixed ``service`` (:data:`SERVICE`) and a composed ``username`` of the
form ``{group}.{instance?}.{name}`` so a credential group can host several
named values, optionally namespaced by instance (e.g. several mail accounts).

This module deliberately knows **nothing** about files or ``~/.axm``: any
disk layout (config directories, token files) is owned by ``axm-config``.
:func:`atomic_write` is the single disk primitive vault exposes, for the
OAuth refresh-token rotation case where a caller — given a path by
``axm-config`` — needs a crash-safe overwrite. It does not resolve or create
that path.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import keyring
from keyring.errors import InitError, NoKeyringError, PasswordDeleteError

__all__ = [
    "SERVICE",
    "KeyringStore",
    "KeyringUnavailableError",
    "atomic_write",
    "rotate_secret",
]

SERVICE = "axm-vault"
"""The fixed keyring service name under which every AXM secret is stored."""

_PREV_SUFFIX = ".prev"
"""Reserved suffix for the one-cycle rotation backup slot (:func:`rotate_secret`)."""


def _escape_segment(segment: str) -> str:
    """Percent-encode the separator characters in a single username segment.

    ``%`` is encoded first (so the encoding is reversible), then the ``.``
    separator. The mapping is injective, so distinct segments stay distinct
    and distinct tuples can never collide on the joined username.
    """
    return segment.replace("%", "%25").replace(".", "%2E")


class KeyringUnavailableError(RuntimeError):
    """The OS keyring backend is unavailable (headless host / no Keychain).

    Raised in place of a raw backend traceback (e.g. ``keyring`` reporting
    ``No recommended backend was available``) so callers can degrade the
    keyring layer gracefully. The message is fixed and actionable; it never
    carries a credential value (never-leak invariant).
    """


@contextlib.contextmanager
def _keyring_guard() -> Iterator[None]:
    """Translate a *no usable backend* keyring failure into a typed error.

    Only the unavailability errors (``NoKeyringError``/``InitError``) are
    remapped to :class:`KeyringUnavailableError`; operational errors such as
    ``PasswordDeleteError`` propagate unchanged. The original exception is
    chained but never interpolated into the message, so no value can leak.
    """
    try:
        yield
    except (NoKeyringError, InitError) as exc:
        raise KeyringUnavailableError(
            "OS keyring backend unavailable (no Keychain/secret service); "
            "set the credential via its environment variable instead"
        ) from exc


class KeyringStore:
    """Store and retrieve secrets in the OS keyring under :data:`SERVICE`.

    The store is stateless: every call delegates to the process-wide
    ``keyring`` backend, so tests can swap in an in-memory backend via
    ``keyring.set_keyring(...)`` without touching the real Keychain.
    """

    @staticmethod
    def username(group: str, name: str, instance: str | None = None) -> str:
        """Compose the keyring ``username`` for a credential.

        The instance segment is omitted cleanly when ``instance`` is ``None``
        (``{group}.{name}``) and inserted between group and name otherwise
        (``{group}.{instance}.{name}``).

        ``.`` is the structural separator, so each segment is percent-escaped
        before joining: a literal ``.`` (or ``%``) inside any segment is
        encoded so that distinct ``(group, name, instance)`` tuples can never
        collapse onto the same username (e.g. ``("a.b", "c")`` vs
        ``("a", "b.c")``). The encoding is reversible and leaves dot-free
        segments untouched, so existing usernames are unchanged and the
        reserved ``.prev`` rotation slot stays distinct from its base name.
        """
        parts = [group, instance, name] if instance is not None else [group, name]
        return ".".join(_escape_segment(part) for part in parts)

    def set(
        self, group: str, name: str, value: str, instance: str | None = None
    ) -> None:
        """Store ``value`` under ``(group, name[, instance])`` in the keyring.

        Raises :class:`KeyringUnavailableError` when no usable backend exists
        (headless host) rather than surfacing a raw backend traceback.
        """
        with _keyring_guard():
            keyring.set_password(SERVICE, self.username(group, name, instance), value)

    def get(self, group: str, name: str, instance: str | None = None) -> str | None:
        """Return the stored secret, or ``None`` if no such credential exists.

        Raises :class:`KeyringUnavailableError` when no usable backend exists
        (headless host) rather than surfacing a raw backend traceback.
        """
        with _keyring_guard():
            return keyring.get_password(SERVICE, self.username(group, name, instance))

    def delete(self, group: str, name: str, instance: str | None = None) -> None:
        """Remove the credential from the keyring (no-op if already absent).

        The real macOS Keychain backend raises
        :class:`keyring.errors.PasswordDeleteError` (``Item not found``) when
        the credential is absent; it is suppressed here so the call is a true
        no-op, as the contract promises and as rotation/cleanup callers rely on.
        """
        with _keyring_guard(), contextlib.suppress(PasswordDeleteError):
            keyring.delete_password(SERVICE, self.username(group, name, instance))


def rotate_secret(
    group: str, name: str, value: str, instance: str | None = None
) -> None:
    """Rotate a keyring secret, retaining the previous value for one cycle.

    The prior cycle's backup is purged first, the current value (if any) is
    copied to the reserved ``{name}.prev`` slot, then ``value`` is written over
    ``{name}``. Retention is strictly one cycle: a stale ``.prev`` never
    lingers across rotations. Keeping the previous secret one rotation lets a
    caller fall back during an in-flight credential roll. No value is ever
    returned or logged.

    Raises:
        ValueError: if ``name`` already ends with the reserved ``.prev``
            suffix — that namespace is owned by the rotation backup slot and
            must not collide with a real spec name or instance.
        KeyringUnavailableError: when the OS keyring backend is unavailable.
    """
    if name.endswith(_PREV_SUFFIX):
        raise ValueError(
            f"cannot rotate {name!r}: the {_PREV_SUFFIX!r} suffix is reserved "
            "for the rotation backup slot"
        )
    store = KeyringStore()
    prev_name = f"{name}{_PREV_SUFFIX}"
    current = store.get(group, name, instance)
    # Purge the prior cycle's backup before writing the new one so retention
    # stays strictly one cycle (a no-op when absent).
    store.delete(group, prev_name, instance)
    if current is not None:
        store.set(group, prev_name, current, instance)
    store.set(group, name, value, instance)


def atomic_write(path: Path | str, data: str, *, encoding: str = "utf-8") -> None:
    """Write ``data`` to ``path`` atomically (temp file + ``os.replace``).

    The write goes to a temporary file in the destination directory, is flushed
    and ``fsync``-ed, then atomically renamed over ``path`` so a concurrent
    reader never observes a partially written file. After the rename the parent
    directory is itself ``fsync``-ed so the new directory entry is durable —
    without that, a crash right after ``os.replace`` could lose the rename even
    though the file content reached disk. The destination directory must
    already exist — vault does not create it (that is ``axm-config``'s
    responsibility). Intended for the OAuth refresh-token rotation case.
    """
    target = Path(path)
    directory = target.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=directory, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
        # Refresh-token leak guard: enforce owner-only perms regardless of
        # umask. mkstemp already creates the temp file 0600; re-chmod after
        # replace mirrors axm-config's store.py so the final inode is 0600.
        os.chmod(target, 0o600)
        # Crash-safety: fsync the parent directory so the new directory entry
        # (the rename) is durable, not just the file content fsync-ed above.
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise
