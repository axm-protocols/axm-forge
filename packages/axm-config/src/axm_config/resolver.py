"""Config resolution with ``env > file > default`` precedence.

The resolver layers three sources for a ``(namespace, key)`` pair:

1. the process environment, under a deterministic name
   ``AXM_<NS upper, dots->underscores>_<KEY upper>``;
2. the ``[ns]`` section of the single ``~/.axm/config.toml`` (via
   :class:`axm_config.store.NamespaceStore`);
3. an explicit ``default``.

:func:`get` / :func:`set_` are the bare key-value surface; :func:`load`
populates a consumer's pydantic model, resolving each field by name and
raising :class:`ConfigError` when a required field stays unresolved.

Note: an environment value is returned as the raw ``str`` from
``os.environ``. Type coercion happens only in :func:`load`, where pydantic
validates the assembled mapping.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from axm_config.store import NamespaceStore

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = [
    "ConfigError",
    "UnsafeHomeError",
    "delete",
    "get",
    "load",
    "set_",
    "validate_segment",
]

_store = NamespaceStore()

_MISSING = object()

#: A safe ``namespace``/``key`` segment. Both patterns are **lowercase-only**
#: (no upper-case, so ``"Demo"`` and ``"demo"`` cannot fold to the same
#: ``AXM_DEMO_*`` prefix) and reject path separators (``/``, ``\``), traversal
#: (``..``), the empty string, and NUL.
# A *namespace* (:data:`_NAMESPACE_RE`) is lowercase-alphanumeric segments
# joined by dots -- no ``_`` and no ``-``; dots fold to ``__`` when deriving the
# env name. A *key* (:data:`_KEY_RE`) is lowercase-alphanumeric segments joined
# by a **single** ``_`` (no ``.``/``-``, no leading/trailing/doubled ``_``) so
# the derived env name stays POSIX-valid and the ns/key boundary is
# recoverable: only the namespace's dot-fold yields ``__``, a key can never
# forge one, and the lone single ``_`` separates the folded namespace from the
# key.
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")
_KEY_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
_SEGMENT_PATTERNS = {"namespace": _NAMESPACE_RE, "key": _KEY_RE}


class ConfigError(RuntimeError):
    """Raised when a required config value cannot be resolved."""


class UnsafeHomeError(ConfigError):
    """Raised when ``~/.axm`` cannot be used safely (e.g. a HOME in a git repo).

    A :class:`ConfigError` subclass so every consumer surface that already
    catches :class:`ConfigError` (the CLI, :func:`load`) degrades cleanly
    instead of leaking the raw ``ValueError`` from
    :func:`axm_config.home.resolve_safe`. The security refusal itself is
    intentional; only its *type* is narrowed here so callers can handle it.
    """


def validate_segment(value: str, *, kind: str = "segment") -> str:
    """Return ``value`` if it is a safe config segment, else raise ConfigError.

    A *segment* is a ``namespace`` or a ``key``: the single entry-point guard
    against path traversal and env-name ambiguity. It must be a non-empty
    ``str`` matching its kind's pattern — no path separators, no ``..``
    traversal, no NUL byte — so it can never widen the on-disk
    ``~/.axm/<ns>.toml`` path. Both patterns are **lowercase-only** (no
    upper-case): the env-name surface upper-cases the segments, so accepting
    both ``"Demo"`` and ``"demo"`` would let two distinct namespaces fold to
    the *same* ``AXM_DEMO_*`` prefix — forbidding upper-case makes that
    collision unrepresentable. The patterns differ by ``kind``: a
    ``"namespace"`` (:data:`_NAMESPACE_RE`) is lowercase-alphanumeric segments
    joined by dots — no ``_`` and no ``-`` — whereas a ``"key"``
    (:data:`_KEY_RE`) is lowercase-alphanumeric segments joined by **single**
    ``_`` (no ``.``/``-``, no leading/trailing ``_``, no doubled ``__``) so the
    derived env name stays POSIX-valid and the ns/key boundary is
    unambiguous: only the namespace's dot-fold yields ``__``, the key can
    never forge one, and the lone single ``_`` separates the folded namespace
    from the key. Any other ``kind`` falls back to the namespace pattern.
    Shared with every public boundary (and reused by the env-name surface) so
    validation is declared exactly once.
    """
    pattern = _SEGMENT_PATTERNS.get(kind, _NAMESPACE_RE)
    if not isinstance(value, str) or not pattern.match(value):
        msg = f"invalid {kind} {value!r}: must match {pattern.pattern}"
        raise ConfigError(msg)
    return value


def _env_name(ns: str, key: str) -> str:
    """Derive the env var name ``AXM_<NS>_<KEY>`` for ``ns``/``key``.

    The namespace is upper-cased with each dot mapped to a *double* underscore,
    the key is upper-cased; both are joined under the ``AXM_`` prefix. The map
    is **provably injective** and always POSIX-valid because the segment rules
    (:func:`validate_segment`) leave exactly one way to read any output back:

    * **No upper-case ambiguity** — both segments are lowercase-only, so the
      upper-casing here is a bijection on the input charset; ``"Demo"`` is
      rejected upstream and cannot share ``AXM_DEMO_*`` with ``"demo"``.
    * **Only dots fold to ``__``** — a namespace (:data:`_NAMESPACE_RE`) is
      lowercase-alphanumeric segments joined by dots, carrying no literal
      ``_`` and no ``-``; a key (:data:`_KEY_RE`) is lowercase-alphanumeric
      segments joined by **single** ``_`` (no leading/trailing/doubled ``_``).
      So a ``__`` in the output can only come from a namespace dot, never from
      a key, and the *single* ``_`` boundary before the key is the only single
      underscore in the namespace part.

    Therefore ``AXM_<ns dots->__>_<key>`` round-trips to exactly one
    ``(ns, key)`` pair, and the result never leaves the POSIX identifier set
    ``^[A-Z_][A-Z0-9_]*$``. Deterministic, injective and POSIX-valid.
    """
    ns_part = ns.upper().replace(".", "__")
    return f"AXM_{ns_part}_{key.upper()}"


def resolve(ns: str, key: str, default: object = None) -> object:
    """Resolve ``key`` in ``ns`` with ``env > file > default`` precedence.

    Validates ``ns`` and ``key`` at this boundary (covers :func:`get` and
    :func:`load`), then returns the env value (raw ``str``) if set, else the
    file value from the namespace store, else ``default``.
    """
    validate_segment(ns, kind="namespace")
    validate_segment(key, kind="key")
    env_value = os.environ.get(_env_name(ns, key), _MISSING)
    if env_value is not _MISSING:
        return env_value
    file_value = _store.read(ns).get(key, _MISSING)
    if file_value is not _MISSING:
        return file_value
    return default


def get(namespace: str, key: str, *, default: object = None) -> object:
    """Return the resolved value for ``key`` in ``namespace``.

    Precedence is ``env > file > default``. An env value is returned as the
    raw ``str`` from the environment; file values keep their TOML-parsed type.
    """
    return resolve(namespace, key, default)


def set_(namespace: str, key: str, value: object) -> None:
    """Persist ``key`` = ``value`` in the ``[namespace]`` section of config.toml.

    ``namespace`` and ``key`` are validated against the safe-segment pattern
    first (path-traversal guard). A ``value`` of ``None`` is routed to
    :func:`delete` — TOML cannot encode ``None``, so deleting the key is the
    well-defined contract rather than a raw ``TypeError``. Otherwise delegates
    to :meth:`NamespaceStore.write` (atomic, ``0600``, other keys preserved).
    """
    validate_segment(namespace, kind="namespace")
    validate_segment(key, kind="key")
    if value is None:
        _store.delete(namespace, key)
        return
    _store.write(namespace, key, value)


def delete(namespace: str, key: str) -> None:
    """Remove ``key`` from the ``[namespace]`` section of config.toml (no-op if absent).

    ``namespace`` and ``key`` are validated first. Deleting an absent key (or a
    namespace with no file) is a silent no-op — it never raises. After removal
    the key resolves through the lower layers again (env, then ``default``).
    """
    validate_segment(namespace, kind="namespace")
    validate_segment(key, kind="key")
    _store.delete(namespace, key)


def load[M: BaseModel](namespace: str, model: type[M]) -> M:
    """Build ``model`` from ``namespace``, resolving each field by name.

    Every field of ``model`` is resolved via :func:`get` (the field name is
    the config key). Unresolved fields are omitted so pydantic applies the
    field default; a required field that stays unresolved raises
    :class:`ConfigError` instead of a raw ``ValidationError``.
    """
    values: dict[str, object] = {}
    for field in model.model_fields:
        resolved = resolve(namespace, field, _MISSING)
        if resolved is not _MISSING:
            values[field] = resolved
    try:
        return model.model_validate(values)
    except Exception as exc:
        msg = f"cannot build {model.__name__} for namespace {namespace!r}: {exc}"
        raise ConfigError(msg) from exc
