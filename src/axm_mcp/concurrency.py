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
        self._timeout = timeout

    def _get(self, key: str) -> asyncio.Lock:
        """Return (or create) the lock for *key*."""
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    @asynccontextmanager
    async def __call__(self, key: str) -> AsyncIterator[None]:
        """Acquire the lock for *key*, with optional timeout.

        Raises:
            asyncio.TimeoutError: If *timeout* is set and exceeded.
        """
        lock = self._get(key)
        if self._timeout is not None:
            await asyncio.wait_for(lock.acquire(), timeout=self._timeout)
            try:
                yield
            finally:
                lock.release()
        else:
            async with lock:
                yield

    def __len__(self) -> int:
        """Number of tracked keys (including idle locks)."""
        return len(self._locks)

    def prune(self) -> int:
        """Remove unlocked (idle) entries. Returns count removed."""
        idle = [k for k, v in self._locks.items() if not v.locked()]
        for k in idle:
            del self._locks[k]
        return len(idle)
