from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeToolResult:
    """Minimal ToolResult stand-in with optional text field."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    hint: str | None = None
    text: str | None = None


class FakeTool:
    """AXMTool-like object with .execute()."""

    def __init__(self, result: FakeToolResult) -> None:
        self._result = result

    def execute(self, **kwargs: Any) -> FakeToolResult:
        """Run the tool."""
        return self._result


def _capture_wrapper(
    name: str,
    tool: Any,
    **register_kwargs: Any,
) -> Any:
    """Register *tool* via ``_register_one`` and return the captured wrapper."""
    from axm_mcp.discovery import _register_one

    captured: dict[str, Any] = {}

    class _FakeMCP:
        def tool(self, *, name: str) -> Callable[[Any], Any]:
            def _decorator(fn: Any) -> Any:
                captured["wrapper"] = fn
                return fn

            return _decorator

    mcp = _FakeMCP()
    _register_one(mcp, name, tool, **register_kwargs)
    return captured["wrapper"]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@patch("axm_mcp.discovery._log_external_step")
def test_wrapper_returns_text_when_set(mock_log: MagicMock) -> None:
    """When ToolResult.text is not None, _wrapper returns the text string."""
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("my_tool", tool)

    out = wrapper()
    assert out == "k: 1"
    assert isinstance(out, str)


@patch("axm_mcp.discovery._log_external_step")
def test_wrapper_returns_dict_when_text_none(mock_log: MagicMock) -> None:
    """When ToolResult.text is None, _wrapper returns the flattened dict."""
    result = FakeToolResult(success=True, data={"k": 1})
    tool = FakeTool(result)
    wrapper = _capture_wrapper("my_tool", tool)

    out = wrapper()
    assert isinstance(out, dict)
    assert out == {"success": True, "k": 1}


@patch("axm_mcp.discovery._log_external_step")
def test_wrapper_plain_branch_unchanged(mock_log: MagicMock) -> None:
    """Plain dispatcher functions still return dict as before."""

    def plain_fn(**kwargs: Any) -> dict[str, Any]:
        """A plain tool."""
        return {"status": "ok", "val": kwargs.get("x", 0)}

    wrapper = _capture_wrapper("plain_tool", plain_fn)

    out = wrapper(x=42)
    assert isinstance(out, dict)
    assert out == {"status": "ok", "val": 42}


@patch("axm_mcp.discovery._log_external_step")
def test_wrapper_text_tracing(mock_log: MagicMock) -> None:
    """When text is set and tracing is active, _log_external_step receives the text."""
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    # Use a non-protocol name so _should_trace=True
    wrapper = _capture_wrapper("traced_tool", tool)

    wrapper()

    mock_log.assert_called_once()
    call_args = mock_log.call_args
    # Positional: (name, kwargs, success, output_str, duration_ms)
    assert call_args[0][0] == "traced_tool"  # tool name
    assert call_args[0][2] is True  # success
    assert call_args[0][3] == "k: 1"  # output — should be the text


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


@patch("axm_mcp.discovery._log_external_step")
def test_text_roundtrip_mcp(mock_log: MagicMock) -> None:
    """Register tool with text output, call via FastMCP ToolManager.

    Response should contain TextContent with raw text, no JSON wrapping.
    """
    from mcp.server.fastmcp import FastMCP

    from axm_mcp.discovery import _register_one

    mcp = FastMCP("test-text")
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    _register_one(mcp, "text_tool", tool)

    async def _run() -> Any:
        content_list, _raw = await mcp._tool_manager.call_tool(
            "text_tool", {}, convert_result=True
        )
        return content_list

    content_list = asyncio.run(_run())
    # FastMCP converts str return → TextContent(text=str), no JSON wrapping
    assert len(content_list) == 1
    content = content_list[0]
    assert content.type == "text"
    assert content.text == "k: 1"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("axm_mcp.discovery._log_external_step")
def test_empty_string_text(mock_log: MagicMock) -> None:
    """Empty string text is not None — text path should fire."""
    result = FakeToolResult(success=True, data={"k": 1}, text="")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("my_tool", tool)

    out = wrapper()
    assert out == ""
    assert isinstance(out, str)


@patch("axm_mcp.discovery._log_external_step")
def test_text_with_error(mock_log: MagicMock) -> None:
    """When text is set even on error, return the text string."""
    result = FakeToolResult(success=False, data={}, error="bad", text="Error: bad")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("my_tool", tool)

    out = wrapper()
    assert out == "Error: bad"
    assert isinstance(out, str)


@patch("axm_mcp.discovery._log_external_step")
@patch("axm_mcp.discovery._HTTP_MODE", True)
def test_async_lock_path_with_text(mock_log: MagicMock) -> None:
    """Async lock wrapper propagates str return type in HTTP mode."""
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    # protocol_ prefix triggers the async lock wrapper
    wrapper = _capture_wrapper("protocol_test", tool)

    async def _run() -> Any:
        return await wrapper(session_id="sess-1")

    out = asyncio.run(_run())
    assert out == "k: 1"
    assert isinstance(out, str)
