"""Process-wide serialization of scaffold writes by canonical target root.

Every scaffold kind writing into a project root shares this single registry,
so a learning-profile write and a protocol-profile write aimed at the same
root exclude each other instead of each holding its own private lock.
"""

from __future__ import annotations

import _thread
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

__all__ = ["target_root_lock"]


@dataclass
class _RootLockEntry:
    lock: _thread.RLock
    users: int = 0


_ROOT_LOCKS: dict[Path, _RootLockEntry] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


@contextmanager
def target_root_lock(root: Path) -> Iterator[None]:
    """Hold the process-wide lock guarding writes on the canonical *root*.

    Args:
        root: The target root, resolved before lookup so that distinct
            spellings of one directory share a single lock.

    Yields:
        ``None``, while the caller owns the root exclusively.
    """
    canonical_root = root.resolve()
    with _ROOT_LOCKS_GUARD:
        entry = _ROOT_LOCKS.get(canonical_root)
        if entry is None:
            entry = _RootLockEntry(lock=_thread.RLock())
            _ROOT_LOCKS[canonical_root] = entry
        entry.users += 1
    entry.lock.acquire()
    try:
        yield
    finally:
        entry.lock.release()
        with _ROOT_LOCKS_GUARD:
            entry.users -= 1
            if entry.users == 0:
                _ROOT_LOCKS.pop(canonical_root, None)
