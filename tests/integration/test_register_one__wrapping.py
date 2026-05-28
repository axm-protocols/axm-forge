from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_mcp import wrapping as _wrapping
from axm_mcp.discovery import _register_one

pytestmark = pytest.mark.integration


class _FakeSessionTool:
    """Minimal AXMTool stub with execute()."""

    name = "protocol_check"

    def execute(self, *, session_id: str = "", outputs: str = "") -> Any:
        """Fake protocol_check."""
        result = MagicMock()
        result.success = True
        result.data = {"session_id": session_id}
        result.error = None
        result.hint = None
        return result


class TestLockSkippedStdioMode:
    """AC4: No lock acquired in stdio mode."""

    @pytest.mark.asyncio
    async def test_no_lock_in_stdio(self) -> None:
        """protocol tool runs without lock when _HTTP_MODE is False."""
        original = _wrapping._HTTP_MODE
        try:
            _wrapping._HTTP_MODE = False
            mock_mcp = MagicMock()
            tool = _FakeSessionTool()
            _register_one(mock_mcp, "protocol_check", tool)

            wrapper = mock_mcp.tool.return_value.call_args[0][0]
            # In stdio mode the wrapper is async but skips the lock.
            result = await wrapper(session_id="s1", outputs="{}")
            assert result["success"] is True
            assert _wrapping._session_lock._locks.get("s1") is None
        finally:
            _wrapping._HTTP_MODE = original


class TestLockKeyNone:
    """Edge case: protocol tool called without session_id."""

    @pytest.mark.asyncio
    async def test_no_key_skips_lock(self) -> None:
        """When session_id is missing, no lock is acquired."""
        original = _wrapping._HTTP_MODE
        try:
            _wrapping._HTTP_MODE = True
            mock_mcp = MagicMock()
            tool = _FakeSessionTool()
            _register_one(mock_mcp, "protocol_check", tool)

            wrapper = mock_mcp.tool.return_value.call_args[0][0]
            result = await wrapper(outputs="{}")
            assert result["success"] is True
        finally:
            _wrapping._HTTP_MODE = original


class TestConcurrentProtocolCheck:
    """Functional: Two concurrent protocol_check(session_id=X) serialize."""

    @pytest.mark.asyncio
    async def test_concurrent_same_session(self) -> None:
        """Both complete without corruption, serialized by lock."""
        original = _wrapping._HTTP_MODE
        try:
            _wrapping._HTTP_MODE = True
            order: list[str] = []

            class SlowTool:
                name = "protocol_check"

                def execute(self, **kwargs: Any) -> Any:
                    sid = kwargs.get("session_id", "?")
                    order.append(f"{sid}-start")
                    # Simulate work (sync — runs in thread via to_thread)
                    import time

                    time.sleep(0.05)
                    order.append(f"{sid}-end")
                    result = MagicMock()
                    result.success = True
                    result.data = {"ok": True}
                    result.error = None
                    result.hint = None
                    return result

            mock_mcp = MagicMock()
            _register_one(mock_mcp, "protocol_check", SlowTool())
            wrapper = mock_mcp.tool.return_value.call_args[0][0]

            await asyncio.gather(
                wrapper(session_id="X", outputs="{}"),
                wrapper(session_id="X", outputs="{}"),
            )
            # Serialized: first ends before second starts.
            assert order[1] == "X-end"
            assert order[2] == "X-start"
        finally:
            _wrapping._HTTP_MODE = original
