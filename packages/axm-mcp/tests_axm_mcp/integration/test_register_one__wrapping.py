from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_mcp import wrapping as _wrapping
from axm_mcp.discovery import register_one

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
            register_one(mock_mcp, "protocol_check", tool)

            wrapper = mock_mcp.tool.return_value.call_args[0][0]
            # In stdio mode the wrapper runs the tool inline and skips the
            # lock path entirely. The locked path is the only branch that
            # offloads to a worker thread, so asyncio.to_thread is never
            # touched: asserting it is uncalled proves no lock was acquired,
            # without probing the lock manager's internal state.
            with patch("axm_mcp.wrapping.asyncio.to_thread") as to_thread:
                result = await wrapper(session_id="s1", outputs="{}")
            assert result["success"] is True
            to_thread.assert_not_called()
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
            register_one(mock_mcp, "protocol_check", tool)

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
            register_one(mock_mcp, "protocol_check", SlowTool())
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


@pytest.mark.asyncio
async def test_registered_shared_wrapper_isolates_real_session_perimeters(
    tmp_path: Path,
) -> None:
    """AC1: a registered shared wrapper enforces the emitting session perimeter."""
    from axm.tools.base import ToolResult
    from axm.tools.write_scope import WriteContract

    from axm_mcp.session_contracts import SessionContractRegistry
    from axm_mcp.wrapping import build_wrappers

    perimeter_a = tmp_path / "a"
    perimeter_b = tmp_path / "b"
    perimeter_a.mkdir()
    perimeter_b.mkdir()
    registry = SessionContractRegistry(clock=lambda: 0.0)
    registry.bind(
        "s-a",
        WriteContract.from_mapping(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": [str(perimeter_a)],
            }
        ),
    )
    registry.bind(
        "s-b",
        WriteContract.from_mapping(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": [str(perimeter_b)],
            }
        ),
    )
    current_session = {"id": "s-a"}

    class FilesystemWriter:
        def execute(self, *, path: str, file: str, content: str) -> ToolResult:
            Path(path, file).write_text(content, encoding="utf-8")
            return ToolResult(success=True, text="written")

    def shared_build(name: str, tool: Any) -> tuple[Any, Any]:
        return build_wrappers(
            name,
            tool,
            shared_mode=True,
            write_contract_resolver=lambda: registry.resolve(current_session["id"]),
        )

    mock_mcp = MagicMock()
    with patch("axm_mcp.discovery.build_wrappers", side_effect=shared_build):
        register_one(mock_mcp, "write_file", FilesystemWriter())
    wrapper = mock_mcp.tool.return_value.call_args[0][0]
    target = perimeter_b / "out.txt"

    refused = await wrapper(
        path=str(perimeter_b),
        file=target.name,
        content="owned-by-b",
    )

    assert isinstance(refused, dict)
    assert refused["success"] is False
    assert not target.exists()

    current_session["id"] = "s-b"
    allowed = await wrapper(
        path=str(perimeter_b),
        file=target.name,
        content="owned-by-b",
    )

    assert allowed == "written"
    assert target.read_text(encoding="utf-8") == "owned-by-b"
