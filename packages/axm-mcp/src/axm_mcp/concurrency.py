from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

__all__ = ["KeyedLock"]

_DEFAULT_TIMEOUT: float = 30.0


class KeyedLock:
    """Per-key asyncio lock manager.

    Provides a separate ``asyncio.Lock`` for each key, created lazily.
    Concurrent operations on *different* keys proceed in parallel;
    operations on the *same* key are serialized.

    Args:
        timeout: Maximum seconds to wait for a lock.
            ``None`` disables the timeout.
    """

    def __init__(self, timeout: float | None = _DEFAULT_TIMEOUT) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._refs: dict[str, int] = {}
        self._timeout = timeout

    def _acquire_ref(self, key: str) -> asyncio.Lock:
        """Return (or create) the lock for *key* and register a reference.

        Incrementing ``_refs`` synchronously here — before any ``await`` on
        ``acquire`` — pins the entry for the whole acquire→release window,
        so a key being awaited is never reaped (AC2). The single-threaded
        event loop makes this read-modify-write atomic between awaits.
        """
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        self._refs[key] = self._refs.get(key, 0) + 1
        return lock

    def _release_ref(self, key: str) -> None:
        """Drop one reference; reap the entry once no holder/waiter remains."""
        remaining = self._refs.get(key, 1) - 1
        if remaining <= 0:
            self._refs.pop(key, None)
            self._locks.pop(key, None)
        else:
            self._refs[key] = remaining

    @asynccontextmanager
    async def __call__(self, key: str) -> AsyncIterator[None]:
        """Acquire the lock for *key*, with optional timeout.

        Idle entries are reaped opportunistically on release once no
        coroutine holds or awaits the key, so the map stays bounded
        under a long-running server without any external ``prune()``.

        Raises:
            asyncio.TimeoutError: If *timeout* is set and exceeded.
        """
        lock = self._acquire_ref(key)
        try:
            if self._timeout is not None:
                await asyncio.wait_for(lock.acquire(), timeout=self._timeout)
                try:
                    yield
                finally:
                    lock.release()
            else:
                async with lock:
                    yield
        finally:
            self._release_ref(key)

    def __len__(self) -> int:
        """Number of tracked keys (including idle locks)."""
        return len(self._locks)

    def prune(self) -> int:
        """Remove idle entries (no holder, no waiter). Returns count removed.

        Retained for compatibility: opportunistic reaping on release already
        bounds the map, so this is normally a no-op. An entry is idle only
        when unlocked *and* its reference count is zero — a held or awaited
        key is never removed.
        """
        idle = [
            k
            for k, v in self._locks.items()
            if not v.locked() and self._refs.get(k, 0) == 0
        ]
        for k in idle:
            self._locks.pop(k, None)
            self._refs.pop(k, None)
        return len(idle)
