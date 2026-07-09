"""Atomic single-file TOML store under ``~/.axm/config.toml``.

:class:`NamespaceStore` reads and writes a single ``~/.axm/config.toml`` whose
top-level tables are the namespaces (a dotted namespace such as
``storage.portfolio`` maps to the nested table ``[storage.portfolio]``). It
degrades gracefully (returning ``{}``) when the file, or a namespace section,
is absent or corrupt, and writes atomically (same-dir temp file +
:func:`os.replace`) with a ``0600`` mode on the resulting file. The containing
``~/.axm`` directory is resolved (and locked to ``0700``) via
:func:`axm_config.home.axm_home`.

Migration: a legacy per-namespace file ``~/.axm/<ns>.toml`` (the previous
layout) is still readable through :meth:`read`; on the next :meth:`write`/
:meth:`delete` for that namespace its contents are folded into ``config.toml``
and the legacy file is removed — no silent data loss.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from tempfile import NamedTemporaryFile

import tomli_w

from axm_config.home import axm_home, resolve_safe

__all__ = ["CONFIG_FILENAME", "NAMESPACE_FILE_MODE", "NamespaceStore"]


def _safe_home() -> Path:
    """Return ``resolve_safe(axm_home())``, re-typing its refusal as ConfigError.

    :func:`~axm_config.home.resolve_safe` raises a bare :class:`ValueError`
    when ``~/.axm`` resolves inside a git checkout (a misconfigured ``HOME``).
    The store re-raises that as :class:`~axm_config.resolver.UnsafeHomeError`
    (a :class:`ConfigError`) so a consumer of ``get``/``load``/the CLI gets the
    documented ``ConfigError`` contract instead of a raw ``ValueError``. The
    import is deferred to break the ``resolver -> store -> resolver`` cycle.
    """
    from axm_config.resolver import UnsafeHomeError

    try:
        return resolve_safe(axm_home())
    except ValueError as exc:
        raise UnsafeHomeError(str(exc)) from exc


NAMESPACE_FILE_MODE = 0o600
CONFIG_FILENAME = "config.toml"


class NamespaceStore:
    """Read/write namespace sections of a single ``~/.axm/config.toml``.

    Each namespace maps to a top-level (or nested, for a dotted namespace)
    TOML table within one ``config.toml``. Reads of an absent or malformed
    file/section return ``{}`` rather than raising, so a consumer can rely on
    the store at import time without a pre-existing ``~/.axm`` directory.
    Writes are atomic, preserve every other section, and leave the file
    ``0600``. A namespace node may be **both** a leaf (its own scalar/array
    keys) **and** a prefix (nested **child** namespaces such as ``[git.default]``
    under ``[git]``): those child sub-tables are re-attached on every write, so
    setting a key under the parent never erases them. Legacy
    ``~/.axm/<ns>.toml`` files are folded in on first write.
    """

    def _config_path(self) -> Path:
        """Resolve the on-disk path of ``config.toml`` under ``axm_home()``.

        Defence in depth on top of the boundary segment validation: the
        resolved path must sit *inside* the resolved ``~/.axm`` home, and
        ``resolve_safe`` refuses a home that itself resolves inside a git
        checkout (a misconfigured ``HOME`` pointing into a repo). A path that
        would escape the home raises :class:`ValueError`.
        """
        home = _safe_home()
        path = (home / CONFIG_FILENAME).resolve()
        if home not in path.parents:
            msg = f"refusing out-of-home store path {path}: escapes {home}"
            raise ValueError(msg)
        return path

    def _legacy_path(self, ns: str) -> Path:
        """Resolve the legacy per-namespace ``~/.axm/<ns>.toml`` path.

        Same in-home containment guard as :meth:`_config_path`. This is the
        previous storage layout; it is read-through and folded into
        ``config.toml`` on the next write.
        """
        home = _safe_home()
        path = (home / f"{ns}.toml").resolve()
        if home not in path.parents:
            msg = f"refusing out-of-home store path {path}: escapes {home}"
            raise ValueError(msg)
        return path

    def _load_config(self) -> dict[str, object]:
        """Return the full parsed ``config.toml`` mapping, or ``{}``.

        A missing file or a malformed TOML payload both degrade to ``{}`` so
        the call never raises for a consumer.
        """
        path = self._config_path()
        try:
            with path.open("rb") as fh:
                return tomllib.load(fh)
        except FileNotFoundError:
            return {}
        except (tomllib.TOMLDecodeError, OSError):
            return {}

    def _read_legacy(self, ns: str) -> dict[str, object]:
        """Return the contents of the legacy ``~/.axm/<ns>.toml``, or ``{}``."""
        path = self._legacy_path(ns)
        try:
            with path.open("rb") as fh:
                return tomllib.load(fh)
        except FileNotFoundError:
            return {}
        except (tomllib.TOMLDecodeError, OSError):
            return {}

    def read(self, ns: str) -> dict[str, object]:
        """Return the section for ``ns``, or ``{}`` if absent/corrupt.

        The ``[ns]`` section of ``config.toml`` is returned as a flat mapping
        of that namespace's *own* keys: a dotted namespace maps to a nested
        table, and any nested sub-table is a **child namespace**, not a key, so
        it is excluded from the result. If the section is absent but a legacy
        ``~/.axm/<ns>.toml`` exists, the legacy contents are returned so the
        value stays visible before the fold. A missing file or a malformed
        TOML payload both degrade to ``{}``. Raises
        :class:`~axm_config.resolver.UnsafeHomeError` (a :class:`ConfigError`)
        only when ``~/.axm`` cannot be used safely (HOME inside a git repo).
        """
        section = _section(self._load_config(), ns)
        if section:
            return section
        return self._read_legacy(ns)

    def write(self, ns: str, key: str, value: object) -> None:
        """Set ``key`` to ``value`` in ``ns``, preserving every other section.

        Read-modify-write of the *whole* ``config.toml``: the full mapping is
        loaded, the ``ns`` section folded with any legacy file and updated, and
        the result serialised to a same-directory temp file atomically moved
        into place via :func:`os.replace`; the file is chmod ``0600``. The
        legacy ``~/.axm/<ns>.toml`` (if any) is removed after the fold.
        """
        config = self._load_config()
        section = self._fold_legacy(config, ns)
        section[key] = value
        _set_section(config, ns, _with_child_tables(config, ns, section))
        self._commit_config(config)
        self._drop_legacy(ns)

    def delete(self, ns: str, key: str) -> None:
        """Remove ``key`` from ``ns``, rewriting atomically (no-op if absent).

        Read-modify-write mirroring :meth:`write` over the whole
        ``config.toml``: the key is popped from the (legacy-folded) section. If
        the section becomes empty it is dropped; if the file then holds no
        section it is unlinked. A missing key (after folding) is a silent
        no-op, but a pending legacy fold is still applied.
        """
        config = self._load_config()
        section = self._fold_legacy(config, ns)
        had_legacy = self._legacy_path(ns).exists()
        if key not in section and not had_legacy:
            return
        section.pop(key, None)
        if section:
            _set_section(config, ns, section)
        else:
            _drop_section(config, ns)
        if config:
            self._commit_config(config)
        else:
            self._config_path().unlink(missing_ok=True)
        self._drop_legacy(ns)

    def namespaces(self) -> list[str]:
        """Return every namespace path present in ``config.toml`` or legacy.

        A leaf table (a mapping whose values are all scalars/arrays, i.e. an
        actual namespace section) yields its dotted path. Legacy
        ``~/.axm/<ns>.toml`` files contribute their stem. Used by the doctor to
        enumerate "all known" namespaces when none is requested.
        """
        found = set(_leaf_paths(self._load_config()))
        home = _safe_home()
        for legacy in home.glob("*.toml"):
            if legacy.name != CONFIG_FILENAME:
                found.add(legacy.stem)
        return sorted(found)

    def _fold_legacy(self, config: dict[str, object], ns: str) -> dict[str, object]:
        """Return the ``ns`` section merged with any legacy file (legacy base)."""
        section = _section(config, ns)
        legacy = self._read_legacy(ns)
        merged: dict[str, object] = {**legacy, **section}
        return merged

    def _drop_legacy(self, ns: str) -> None:
        """Remove the legacy ``~/.axm/<ns>.toml`` after a successful fold."""
        self._legacy_path(ns).unlink(missing_ok=True)

    def _commit_config(self, config: dict[str, object]) -> None:
        """Serialise ``config`` to a same-dir temp file and atomically swap it.

        The mapping is written to a ``NamedTemporaryFile`` under ``~/.axm`` and
        moved onto ``config.toml`` via :func:`os.replace`; the resulting file
        is chmod ``0600``.
        """
        path = self._config_path()
        payload = tomli_w.dumps(config).encode("utf-8")
        with NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        self._commit(tmp_path, path)

    def _commit(self, tmp_path: Path, path: Path) -> None:
        """Atomically move ``tmp_path`` onto ``path``, never leaking the temp.

        :func:`os.replace` is the atomic swap; if it (or the follow-up
        ``chmod``) raises, the staged temp file would otherwise linger under
        ``~/.axm``. A ``try/finally`` unlinks it on the error path while a
        successful replace consumes it (the ``missing_ok`` unlink is then a
        no-op on the already-moved path).
        """
        try:
            os.replace(tmp_path, path)
            if os.name == "posix":
                os.chmod(path, NAMESPACE_FILE_MODE)
        finally:
            tmp_path.unlink(missing_ok=True)


def _section(config: dict[str, object], ns: str) -> dict[str, object]:
    """Return a *copy* of the ``ns`` section's own keys, or ``{}``.

    A dotted ``ns`` walks nested tables (``storage.portfolio`` ->
    ``config["storage"]["portfolio"]``). A missing or non-table node yields
    ``{}``. Nested sub-tables are **child namespaces**, not keys of ``ns`` (a
    node can be both a leaf and a prefix, e.g. ``[a]`` with ``x`` plus
    ``[a.b]``), so they are dropped: the returned dict holds only ``ns``'s own
    scalar/array keys. The result is a shallow copy so callers can mutate it.
    """
    node: object = config
    for segment in ns.split("."):
        if not isinstance(node, dict) or segment not in node:
            return {}
        node = node[segment]
    if not isinstance(node, dict):
        return {}
    return {k: v for k, v in node.items() if not isinstance(v, dict)}


def _raw_node(config: dict[str, object], ns: str) -> dict[str, object]:
    """Return the ``ns`` table node verbatim (child sub-tables kept), or ``{}``.

    Unlike :func:`_section` -- which strips nested sub-tables so it yields only
    ``ns``'s own scalar/array keys -- this returns the node *as stored*,
    including any **child namespace** sub-tables (e.g. ``[git.default]`` under
    ``[git]``). A dotted ``ns`` walks the nested tables; a missing segment or a
    non-table node yields ``{}``. The node is returned by reference for reading,
    not mutation.
    """
    node: object = config
    for segment in ns.split("."):
        if not isinstance(node, dict) or segment not in node:
            return {}
        node = node[segment]
    if not isinstance(node, dict):
        return {}
    return node


def _with_child_tables(
    config: dict[str, object], ns: str, section: dict[str, object]
) -> dict[str, object]:
    """Merge ``section`` over the child sub-tables already stored under ``ns``.

    :func:`_section` / :meth:`NamespaceStore._fold_legacy` yield only ``ns``'s
    own scalar/array keys, so persisting that mapping verbatim via
    :func:`_set_section` would erase any sibling **child namespace** (e.g.
    ``[git.default]`` under ``[git]``). This re-attaches those children: every
    dict-valued child of the raw ``ns`` node that ``section`` does not itself
    provide is preserved, then ``section`` wins for every key it carries
    (``{**preserved, **section}``). With no child sub-tables the result equals
    ``section``.
    """
    node = _raw_node(config, ns)
    preserved = {
        key: value
        for key, value in node.items()
        if isinstance(value, dict) and key not in section
    }
    return {**preserved, **section}


def _set_section(
    config: dict[str, object], ns: str, section: dict[str, object]
) -> None:
    """Set the ``ns`` section of ``config`` to ``section``, creating parents.

    A dotted ``ns`` creates the intermediate nested tables as needed. An
    existing non-table node along the path is overwritten with a table.
    """
    segments = ns.split(".")
    node = config
    for segment in segments[:-1]:
        child = node.get(segment)
        if not isinstance(child, dict):
            child = {}
            node[segment] = child
        node = child
    node[segments[-1]] = section


def _drop_section(config: dict[str, object], ns: str) -> None:
    """Remove the ``ns`` section from ``config``, pruning empty parent tables.

    A dotted ``ns`` is removed leaf-first; any intermediate table left empty by
    the removal is pruned too, so an emptied ``[storage.portfolio]`` does not
    leave a dangling ``[storage]``.
    """
    segments = ns.split(".")
    chain: list[tuple[dict[str, object], str]] = []
    node: object = config
    for segment in segments:
        if not isinstance(node, dict) or segment not in node:
            return
        chain.append((node, segment))
        node = node[segment]
    # Drop the leaf section unconditionally (the caller decided it is empty),
    # then prune any intermediate table the removal left empty.
    leaf_parent, leaf_segment = chain[-1]
    del leaf_parent[leaf_segment]
    for parent, segment in reversed(chain[:-1]):
        child = parent.get(segment)
        if isinstance(child, dict) and child:
            break
        del parent[segment]


def _leaf_paths(config: dict[str, object], prefix: str = "") -> list[str]:
    """Return the dotted paths of every namespace section in ``config``.

    A node can be **both** a namespace (it carries its own scalar/array keys)
    **and** a prefix (it nests further tables) -- e.g. ``[a]`` with ``x`` plus
    ``[a.b]``. Such a node yields *both* its own path and the paths of its
    children, so a mixed parent no longer hides its nested namespaces. A table
    with at least one non-table value yields ``path``; every sub-table is
    recursed into. An empty table is treated as a leaf namespace.
    """
    paths: list[str] = []
    for name, value in config.items():
        if not isinstance(value, dict):
            continue
        path = f"{prefix}{name}"
        sub_tables = {k: v for k, v in value.items() if isinstance(v, dict)}
        has_own_keys = len(sub_tables) < len(value)
        if has_own_keys or not value:
            paths.append(path)
        for child in sub_tables:
            paths.extend(_leaf_paths({child: value[child]}, prefix=f"{path}."))
    return paths
