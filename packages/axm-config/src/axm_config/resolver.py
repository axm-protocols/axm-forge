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
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from axm_config.store import NamespaceStore

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = [
    "ConfigError",
    "ExecutionPolicyOverride",
    "UnsafeHomeError",
    "delete",
    "delete_execution_policy",
    "get",
    "get_execution_policy",
    "list_execution_policies",
    "load",
    "set_",
    "set_execution_policy",
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


if TYPE_CHECKING:

    class _PolicyBase:
        def __init__(self, **data: object) -> None: ...

        def model_dump(self, *, exclude_none: bool = False) -> dict[str, object]: ...

else:
    _PolicyBase = BaseModel


class ExecutionPolicyOverride(_PolicyBase):
    """Typed per-ticket-type execution override."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, strict=True
    )

    backend: str | None = None
    model: str | None = None
    analysis_enabled: bool | None = None

    def __init__(
        self,
        *,
        backend: str | None = None,
        model: str | None = None,
        analysis_enabled: bool | None = None,
        **extra: object,
    ) -> None:
        super().__init__(
            backend=backend,
            model=model,
            analysis_enabled=analysis_enabled,
            **extra,
        )


_POLICY_KEYS = frozenset({"backend", "model", "analysis_enabled"})
_TRUE_TOKENS = frozenset({"true", "1", "yes", "on"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "off"})


_EXECUTION_POLICY_IDENTIFIER_RE = re.compile(
    r"^[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)*$"
)
_EXECUTION_NAMESPACE_PREFIX = "execution.v1."
_EXECUTION_TOKEN_RE = re.compile(r"^[0-9a-f]+$")


def _validate_execution_policy_identifier(ticket_type: str) -> str:
    """Return a valid public ticket-type identifier or raise ConfigError."""
    if (
        not isinstance(ticket_type, str)
        or _EXECUTION_POLICY_IDENTIFIER_RE.fullmatch(ticket_type) is None
    ):
        pattern = _EXECUTION_POLICY_IDENTIFIER_RE.pattern
        msg = (
            f"invalid execution policy identifier {ticket_type!r}: must match {pattern}"
        )
        raise ConfigError(msg)
    return ticket_type


def _encode_execution_policy_identifier(ticket_type: str) -> str:
    """Encode one validated identifier as canonical lowercase UTF-8 hex."""
    validated = _validate_execution_policy_identifier(ticket_type)
    return validated.encode("utf-8").hex()


def _decode_execution_namespace(namespace: str) -> str:
    """Strictly decode one canonical versioned execution namespace."""
    if not isinstance(namespace, str) or not namespace.startswith(
        _EXECUTION_NAMESPACE_PREFIX
    ):
        msg = f"invalid execution namespace {namespace!r}"
        raise ConfigError(msg)

    token = namespace.removeprefix(_EXECUTION_NAMESPACE_PREFIX)
    if not token or len(token) % 2 or _EXECUTION_TOKEN_RE.fullmatch(token) is None:
        msg = f"invalid execution namespace token {token!r}"
        raise ConfigError(msg)

    try:
        ticket_type = bytes.fromhex(token).decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        msg = f"invalid execution namespace token {token!r}"
        raise ConfigError(msg) from exc

    _validate_execution_policy_identifier(ticket_type)
    if _encode_execution_policy_identifier(ticket_type) != token:
        msg = f"non-canonical execution namespace token {token!r}"
        raise ConfigError(msg)
    return ticket_type


def _execution_namespace(ticket_type: str) -> str:
    """Validate a ticket type and return its execution namespace."""
    token = _encode_execution_policy_identifier(ticket_type)
    return f"{_EXECUTION_NAMESPACE_PREFIX}{token}"


def _policy_pair(
    backend: object,
    model: object,
    *,
    layer: str,
) -> tuple[str | None, str | None]:
    """Validate backend/model as one complete, non-blank layer."""
    backend_missing = backend is _MISSING or backend is None
    model_missing = model is _MISSING or model is None
    if backend_missing and model_missing:
        return None, None
    if backend_missing != model_missing:
        msg = f"{layer} execution policy requires both backend and model"
        raise ConfigError(msg)
    if not isinstance(backend, str) or not backend.strip():
        msg = f"{layer} execution policy backend must be a non-blank string"
        raise ConfigError(msg)
    if not isinstance(model, str) or not model.strip():
        msg = f"{layer} execution policy model must be a non-blank string"
        raise ConfigError(msg)
    return backend, model


def _policy_boolean(value: object, *, layer: str) -> bool | None:
    """Validate a stored bool or parse one exact environment bool token."""
    if value is _MISSING or value is None:
        return None
    if isinstance(value, bool):
        return value
    if layer == "environment" and isinstance(value, str):
        if value != value.strip():
            msg = "environment analysis_enabled must not contain whitespace"
            raise ConfigError(msg)
        token = value.lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    msg = f"{layer} analysis_enabled must be a boolean"
    raise ConfigError(msg)


def _policy_from_values(
    values: dict[str, object],
    *,
    layer: str,
) -> ExecutionPolicyOverride:
    """Build a validated override from one configuration layer."""
    unexpected = values.keys() - _POLICY_KEYS
    if unexpected:
        names = ", ".join(sorted(unexpected))
        msg = f"{layer} execution policy has unexpected fields: {names}"
        raise ConfigError(msg)
    backend, model = _policy_pair(
        values.get("backend", _MISSING),
        values.get("model", _MISSING),
        layer=layer,
    )
    analysis_enabled = _policy_boolean(
        values.get("analysis_enabled", _MISSING),
        layer=layer,
    )
    return ExecutionPolicyOverride(
        backend=backend,
        model=model,
        analysis_enabled=analysis_enabled,
    )


def _is_policy_tombstone(values: dict[str, object]) -> bool:
    """Return whether values are the exact versioned deletion sentinel."""
    return values == {"tombstone": "v1"}


def _read_policy_section(namespace: str) -> dict[str, object]:
    """Read one exact stored section, bypassing compatibility overlays."""
    if isinstance(_store, NamespaceStore):
        return _store.read_exact(namespace)
    return _store.read(namespace)


def _policy_file_values(
    ticket_type: str,
    canonical_values: dict[str, object],
) -> dict[str, object]:
    """Select canonical, tombstone, or compatible legacy policy values."""
    if _is_policy_tombstone(canonical_values):
        return {}
    if canonical_values and "tombstone" not in canonical_values:
        return canonical_values
    return _read_policy_section(f"execution.{ticket_type}")


def _canonical_policy_entry(
    namespace: str,
) -> tuple[str, ExecutionPolicyOverride | None] | None:
    """Decode one valid canonical policy or tombstone for listing."""
    try:
        ticket_type = _decode_execution_namespace(namespace)
    except ConfigError:
        return None
    values = _store.read(namespace)
    if _is_policy_tombstone(values):
        return ticket_type, None
    if "tombstone" in values or not _POLICY_KEYS.intersection(values):
        return None
    try:
        return ticket_type, _policy_from_values(values, layer="file")
    except ConfigError:
        return None


def _legacy_policy_entry(
    namespace: str,
) -> tuple[str, ExecutionPolicyOverride] | None:
    """Decode one compatible legacy policy for listing."""
    try:
        ticket_type = _validate_execution_policy_identifier(
            namespace.removeprefix("execution.")
        )
        values = _read_policy_section(namespace)
        if not _POLICY_KEYS.intersection(values):
            return None
        return ticket_type, _policy_from_values(values, layer="file")
    except ConfigError:
        return None


def get_execution_policy(ticket_type: str) -> ExecutionPolicyOverride:
    """Resolve one targeted policy, raising ConfigError for malformed values."""
    namespace = _execution_namespace(ticket_type)
    canonical_values = _store.read(namespace)
    env_backend = os.environ.get(_env_name(namespace, "backend"), _MISSING)
    env_model = os.environ.get(_env_name(namespace, "model"), _MISSING)
    env_analysis = os.environ.get(
        _env_name(namespace, "analysis_enabled"),
        _MISSING,
    )
    env_pair_present = env_backend is not _MISSING or env_model is not _MISSING

    if env_pair_present:
        backend, model = _policy_pair(
            env_backend,
            env_model,
            layer="environment",
        )
    else:
        backend, model = None, None
    if env_analysis is not _MISSING:
        analysis_enabled = _policy_boolean(env_analysis, layer="environment")
    else:
        analysis_enabled = None

    if env_pair_present and env_analysis is not _MISSING:
        return ExecutionPolicyOverride(
            backend=backend,
            model=model,
            analysis_enabled=analysis_enabled,
        )

    file_values = _policy_file_values(ticket_type, canonical_values)
    if not env_pair_present:
        file_policy = _policy_from_values(file_values, layer="file")
        backend, model = file_policy.backend, file_policy.model
    if env_analysis is _MISSING:
        analysis_enabled = _policy_boolean(
            file_values.get("analysis_enabled", _MISSING),
            layer="file",
        )
    return ExecutionPolicyOverride(
        backend=backend,
        model=model,
        analysis_enabled=analysis_enabled,
    )


def set_execution_policy(
    ticket_type: str,
    *,
    backend: str | None = None,
    model: str | None = None,
    analysis_enabled: bool | None = None,
) -> None:
    """Atomically replace or clear one complete ticket-type policy leaf."""
    namespace = _execution_namespace(ticket_type)
    if backend is None and model is None and analysis_enabled is None:
        _store.replace_section(namespace, {"tombstone": "v1"})
        return
    policy = _policy_from_values(
        {
            "backend": backend,
            "model": model,
            "analysis_enabled": analysis_enabled,
        },
        layer="argument",
    )
    _store.replace_section(
        namespace,
        policy.model_dump(exclude_none=True),
    )


def delete_execution_policy(ticket_type: str) -> None:
    """Idempotently delete one policy leaf while preserving descendants."""
    namespace = _execution_namespace(ticket_type)
    _store.replace_section(namespace, {"tombstone": "v1"})


def list_execution_policies() -> dict[str, ExecutionPolicyOverride]:
    """Return valid policies in lexical order, skipping malformed leaves."""
    policies: dict[str, ExecutionPolicyOverride] = {}
    masked: set[str] = set()
    namespaces = _store.namespaces()

    for namespace in namespaces:
        if not namespace.startswith(_EXECUTION_NAMESPACE_PREFIX):
            continue
        entry = _canonical_policy_entry(namespace)
        if entry is None:
            continue
        ticket_type, policy = entry
        masked.add(ticket_type)
        if policy is not None:
            policies[ticket_type] = policy

    for namespace in namespaces:
        if not namespace.startswith("execution.") or namespace.startswith(
            _EXECUTION_NAMESPACE_PREFIX
        ):
            continue
        entry = _legacy_policy_entry(namespace)
        if entry is None:
            continue
        ticket_type, policy = entry
        if ticket_type not in masked:
            policies[ticket_type] = policy

    return dict(sorted(policies.items()))


_EXECUTION_POLICY_PERSISTENCE_CONTRACT = """
Persistence contract:

* Canonical v1 file namespaces use
  ``execution.v1.<ticket-type-utf8-hex>``: the ticket type is UTF-8 encoded
  and represented by strict, lowercase, even-length hexadecimal. Decoding
  rejects malformed hex and identifiers that do not satisfy the ticket-type
  grammar. Canonical environment variables use the same token in uppercase.
* The compatible legacy file namespace is ``execution.<ticket-type>``.
  Resolution precedence is ``environment > canonical file > legacy file``;
  environment values override the backend/model pair as one unit and
  ``analysis_enabled`` independently.
* Migration is non-destructive: legacy bytes are never rewritten or deleted
  by reads, sets, or deletes. A set writes only the canonical v1 namespace.
* Delete writes the exact canonical sentinel ``{"tombstone": "v1"}``, which
  masks compatible legacy data; a later set replaces the tombstone with the
  complete canonical policy; deleting again restores the tombstone.
"""

for _execution_policy_api in (
    get_execution_policy,
    set_execution_policy,
    delete_execution_policy,
    list_execution_policies,
):
    _execution_policy_api.__doc__ = (
        f"{_execution_policy_api.__doc__}\n\n{_EXECUTION_POLICY_PERSISTENCE_CONTRACT}"
    )
del _execution_policy_api


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
