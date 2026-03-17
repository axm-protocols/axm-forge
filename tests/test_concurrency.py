from __future__ import annotations

import asyncio

import pytest

from axm_mcp.concurrency import KeyedLock


class TestKeyedLockDifferentKeys:
    """AC1: KeyedLock provides per-key asyncio locks."""

    @pytest.mark.asyncio
    async def test_different_keys_no_contention(self) -> None:
        """Two different keys can be held simultaneously."""
        lock = KeyedLock(timeout=1.0)
        order: list[str] = []

        async def hold(key: str, label: str) -> None:
            async with lock(key):
                order.append(f"{label}-acquired")
                await asyncio.sleep(0.05)
                order.append(f"{label}-released")

        await asyncio.gather(hold("a", "A"), hold("b", "B"))
        # Both acquired before either released.
        assert order.index("A-acquired") < order.index("B-released")
        assert order.index("B-acquired") < order.index("A-released")


class TestKeyedLockSameKeySerializes:
    """AC1: Same key serializes concurrent access."""

    @pytest.mark.asyncio
    async def test_same_key_serializes(self) -> None:
        """Second task waits for first to release."""
        lock = KeyedLock(timeout=2.0)
        order: list[str] = []

        async def hold(label: str) -> None:
            async with lock("shared"):
                order.append(f"{label}-acquired")
                await asyncio.sleep(0.05)
                order.append(f"{label}-released")

        await asyncio.gather(hold("first"), hold("second"))
        # Strictly serialized: first releases before second acquires.
        assert order.index("first-released") < order.index("second-acquired")


class TestKeyedLockTimeout:
    """AC5: Lock timeout prevents deadlocks."""

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        """Second task times out when lock is held."""
        lock = KeyedLock(timeout=0.1)

        async with lock("k"):
            with pytest.raises(asyncio.TimeoutError):
                async with lock("k"):
                    pass  # pragma: no cover


class TestKeyedLockGrowth:
    """Edge case: lock dict does not grow unbounded."""

    @pytest.mark.asyncio
    async def test_prune_removes_idle(self) -> None:
        """prune() removes unlocked entries."""
        lock = KeyedLock()
        for i in range(100):
            async with lock(str(i)):
                pass
        assert len(lock) == 100
        removed = lock.prune()
        assert removed == 100
        assert len(lock) == 0
