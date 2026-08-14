"""Durable whole-file replacement primitive.

A whole-file rewrite must never leave a half-written module on disk. This
module writes the new bytes to a temporary sibling located in the SAME
directory as the target (so ``os.replace`` stays on one filesystem and is
therefore atomic), fsyncs it, swaps it over the target, then best-effort
fsyncs the containing directory.

The primitive is deliberately a leaf: it knows nothing about operations,
checksums or scope resolution — it takes an already-resolved absolute
:class:`~pathlib.Path` and the bytes to write.
"""

from __future__ import annotations

import contextlib
import os
import stat
from pathlib import Path

__all__ = ["atomic_replace", "temp_sibling_name"]

_TMP_SUFFIX = ".axmtmp"


def temp_sibling_name(target: Path) -> str:
    """Return the hidden temp-sibling file name used to stage ``target``.

    Pure: the filesystem is never touched. The name is a hidden dotfile
    carrying the target's own name and the ``.axmtmp`` marker, so it can never
    collide with ``target.name``.
    """
    return f".{target.name}{_TMP_SUFFIX}"


def _current_mode(target: Path) -> int | None:
    """Return the target's permission bits, or ``None`` if it does not exist."""
    try:
        return stat.S_IMODE(target.stat().st_mode)
    except OSError:
        return None


def _write_and_sync(tmp: Path, data: bytes) -> None:
    """Write ``data`` to ``tmp`` and fsync its file descriptor before closing."""
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(dir_fd: int) -> None:
    """Best-effort fsync of ``directory`` so the rename itself is durable.

    Some filesystems and platforms refuse a directory fsync; that must never
    fail an otherwise successful replacement.
    """
    with contextlib.suppress(OSError):
        os.fsync(dir_fd)


def atomic_replace(target: Path, data: bytes) -> None:
    """Replace ``target`` with ``data`` atomically and durably.

    The original permission bits are preserved. On any failure the target is
    left untouched and no temp sibling survives.
    """
    directory = target.parent
    tmp = directory / temp_sibling_name(target)
    mode = _current_mode(target)
    # Opened BEFORE the temp file so both descriptors stay live at once: the
    # directory fsync must target its own fd, never a number recycled from
    # the already-closed temp file.
    dir_fd: int | None = None
    with contextlib.suppress(OSError):
        dir_fd = os.open(directory, os.O_RDONLY)
    try:
        try:
            _write_and_sync(tmp, data)
            if mode is not None:
                os.chmod(tmp, mode)
            os.replace(tmp, target)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
        if dir_fd is not None:
            _fsync_directory(dir_fd)
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
