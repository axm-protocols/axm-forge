"""Provenance reporting for resolved config keys (read-only).

:func:`config_doctor_data` answers "where would this key resolve from?" for
every key visible in a namespace, following the resolver's own
``env > file > default`` precedence. It is a diagnostic surface: it probes the
layers and reports the *winning* one per key, it never reads a value into a
consumer and never mutates any layer.

The set of reported keys is the union of the namespace's section in
``~/.axm/config.toml`` and any environment variables matching the resolver's
``AXM_<NS>_*`` naming. For an absent namespace both sources are empty, so the
report is ``{}``.
"""

from __future__ import annotations

import os

from axm_config.resolver import _KEY_RE, _env_name, _store, validate_segment

__all__ = ["config_doctor_data"]


def _env_keys(namespace: str) -> set[str]:
    """Return the keys of every ``AXM_<NS>_*`` env var set for ``namespace``.

    The resolver maps ``(ns, key)`` to ``AXM_<NS upper, dots->__>_<KEY upper>``.
    This reverses that map: for each environment variable sharing the
    namespace prefix, the trailing segment is lower-cased back to a key.
    Because a namespace carries no ``_`` of its own (lowercase-alphanumeric
    segments joined by dots, dots folding to ``__``) and a key can never forge
    a ``__`` (lowercase-alphanumeric segments joined by *single* ``_``, no
    edge/doubled ``_``; see :func:`~axm_config.resolver.validate_segment`), the
    ``AXM_<ns>_`` prefix identifies this namespace's own keys. But that prefix
    is *also* a prefix of a **child** namespace's env vars: ``AXM_A_`` starts
    ``AXM_A__B_C`` (namespace ``a.b``, key ``c``), whose trailing ``_b_c``
    would round-trip to a *bogus* leading-underscore key. So each recovered
    suffix is validated against :data:`~axm_config.resolver._KEY_RE`; a suffix
    that is not a legal key (a child namespace's var) is dropped. The surviving
    reverse map round-trips ``_env_name`` exactly.
    """
    prefix = f"AXM_{namespace.upper().replace('.', '__')}_"
    return {
        candidate
        for name in os.environ
        if name.startswith(prefix) and len(name) > len(prefix)
        if _KEY_RE.match(candidate := name[len(prefix) :].lower())
    }


def _provenance(namespace: str, key: str) -> dict[str, object]:
    """Return ``{layer, present}`` for ``key`` per ``env > file > default``.

    Mirrors the resolver's precedence without reading the value: an env var
    wins over a file key, a file key over the implicit default. ``present`` is
    ``False`` only for the ``default`` layer (no source supplies the key).
    """
    if _env_name(namespace, key) in os.environ:
        return {"layer": "env", "present": True}
    if key in _store.read(namespace):
        return {"layer": "file", "present": True}
    return {"layer": "default", "present": False}


def _known_namespaces() -> list[str]:
    """Return every namespace present in ``~/.axm/config.toml`` (or legacy).

    Used when no explicit namespace is requested. Env-only namespaces are not
    enumerable (the prefix is unbounded), so the file layer — the sections of
    the single ``config.toml`` plus any not-yet-folded legacy per-namespace
    files — is the source of truth for "all known".
    """
    return _store.namespaces()


def config_doctor_data(
    namespace: str | None = None,
) -> dict[str, dict[str, object]]:
    """Report the resolution layer of every visible key, read-only.

    For ``namespace``, the reported keys are the union of the namespace's
    ``config.toml`` section keys and its ``AXM_<NS>_*`` environment keys. When
    ``namespace`` is ``None``, every namespace present in ``config.toml`` (or a
    not-yet-folded legacy file) is reported.
    Keys are formatted ``"<ns>.<key>"``; each maps to
    ``{"layer": env|file|default, "present": bool}``. Nothing is mutated.
    """
    if namespace is not None:
        validate_segment(namespace, kind="namespace")
    namespaces = [namespace] if namespace is not None else _known_namespaces()
    report: dict[str, dict[str, object]] = {}
    for ns in namespaces:
        keys = set(_store.read(ns)) | _env_keys(ns)
        for key in sorted(keys):
            report[f"{ns}.{key}"] = _provenance(ns, key)
    return report
