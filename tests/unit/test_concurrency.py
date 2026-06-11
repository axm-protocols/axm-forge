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
    """AC1/AC3: lock dict does not grow unbounded."""

    @pytest.mark.asyncio
    async def test_prune_removes_idle(self) -> None:
        """AC4: prune() remains public and removes any residual idle entries.

        With opportunistic pruning the burst already drains the map, so
        prune() is a no-op here but still callable for compat.
        """
        lock = KeyedLock()
        async with lock("held"):
            # While a key is held its entry is present and locked.
            assert len(lock) == 1
            # prune() must not remove the held entry.
            assert lock.prune() == 0
            assert len(lock) == 1
        # Once released the entry is gone (opportunistic prune on release).
        assert len(lock) == 0
        # prune() stays public and returns 0 on an empty map.
        assert lock.prune() == 0

    @pytest.mark.asyncio
    async def test_locks_bounded_after_burst(self) -> None:
        """AC1/AC3: after acquiring+releasing 100 distinct keys the map is bounded."""
        lock = KeyedLock()
        for i in range(100):
            async with lock(str(i)):
                pass
        # Idle entries are dropped opportunistically, not retained.
        assert len(lock) == 0

    @pytest.mark.asyncio
    async def test_same_key_serializes_across_prune(self) -> None:
        """AC2: same-key serialization holds even while other keys churn/prune."""
        lock = KeyedLock(timeout=2.0)
        order: list[str] = []

        async def hold(label: str) -> None:
            async with lock("shared"):
                order.append(f"{label}-acquired")
                # Churn unrelated keys to trigger opportunistic pruning.
                for i in range(10):
                    async with lock(f"other-{label}-{i}"):
                        pass
                await asyncio.sleep(0.02)
                order.append(f"{label}-released")

        await asyncio.gather(hold("first"), hold("second"))
        # Strict serialization preserved across the churn/prune activity.
        assert order.index("first-released") < order.index("second-acquired")
        # The contended key was never duplicated/leaked.
        assert len(lock) == 0

    @pytest.mark.asyncio
    async def test_held_lock_never_pruned(self) -> None:
        """AC2: a held key survives opportunistic pruning triggered by other keys."""
        lock = KeyedLock(timeout=2.0)

        async with lock("held"):
            # Acquire+release many other keys, churning the map.
            for i in range(50):
                async with lock(f"churn-{i}"):
                    pass
            # The held key must still be tracked and still locked.
            assert len(lock) == 1
            assert lock.prune() == 0
            assert len(lock) == 1
