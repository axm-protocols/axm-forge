"""Atomic per-namespace TOML store under ``~/.axm/<ns>.toml``.

:class:`NamespaceStore` reads and writes small per-namespace config files,
degrading gracefully (returning ``{}``) when a namespace is absent or corrupt,
and writing atomically (same-dir temp file + :func:`os.replace`) with a
``0600`` mode on the resulting file. The containing ``~/.axm`` directory is
resolved (and locked to ``0700``) via :func:`axm_config.home.axm_home`.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from tempfile import NamedTemporaryFile

import tomli_w

from axm_config.home import axm_home, resolve_safe

__all__ = ["NAMESPACE_FILE_MODE", "NamespaceStore"]

NAMESPACE_FILE_MODE = 0o600


class NamespaceStore:
    """Read/write per-namespace TOML files under ``~/.axm``.

    Each namespace maps to a single ``~/.axm/<ns>.toml`` file. Reads of an
    absent or malformed namespace return ``{}`` rather than raising, so a
    consumer can rely on the store at import time without a pre-existing
    ``~/.axm`` directory. Writes are atomic and leave the file ``0600``.
    """

    def _path(self, ns: str) -> Path:
        """Resolve the on-disk path for ``ns``, contained under ``axm_home()``.

        Defence in depth on top of the boundary segment validation: the
        resolved path must sit *inside* the resolved ``~/.axm`` home, and
        ``resolve_safe`` refuses a home that itself resolves inside a git
        checkout (a misconfigured ``HOME`` pointing into a repo). A path that
        would escape the home raises :class:`ValueError`.
        """
        home = resolve_safe(axm_home())
        path = (home / f"{ns}.toml").resolve()
        if home not in path.parents:
            msg = f"refusing out-of-home store path {path}: escapes {home}"
            raise ValueError(msg)
        return path

    def read(self, ns: str) -> dict[str, object]:
        """Return the parsed contents of ``ns``, or ``{}`` if absent/corrupt.

        A missing file or a malformed TOML payload both degrade to ``{}`` so
        the call never raises for a consumer.
        """
        path = self._path(ns)
        try:
            with path.open("rb") as fh:
                return tomllib.load(fh)
        except FileNotFoundError:
            return {}
        except (tomllib.TOMLDecodeError, OSError):
            return {}

    def write(self, ns: str, key: str, value: object) -> None:
        """Set ``key`` to ``value`` in ``ns``, preserving other keys.

        Read-modify-write: existing keys are preserved. The new mapping is
        serialised to a same-directory temp file and atomically moved into
        place via :func:`os.replace`; the resulting file is chmod ``0600``.
        """
        path = self._path(ns)
        data = self.read(ns)
        data[key] = value
        payload = tomli_w.dumps(data).encode("utf-8")
        directory = path.parent
        with NamedTemporaryFile(mode="wb", dir=directory, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        self._commit(tmp_path, path)

    def delete(self, ns: str, key: str) -> None:
        """Remove ``key`` from ``ns``, rewriting atomically (no-op if absent).

        Read-modify-write mirroring :meth:`write`: the key is popped and the
        remaining mapping re-serialised to a same-dir temp file moved into
        place via :func:`os.replace`. If the namespace becomes empty the file
        is unlinked. A missing file or absent key is a silent no-op.
        """
        path = self._path(ns)
        data = self.read(ns)
        if key not in data:
            return
        del data[key]
        if not data:
            path.unlink(missing_ok=True)
            return
        payload = tomli_w.dumps(data).encode("utf-8")
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
