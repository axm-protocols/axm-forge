"""Tests for the MCP tool-call wrapper runtime (axm_mcp.wrapping).

Merged from four aspect-split source files, all dominantly covering
``axm_mcp.wrapping`` (tracing, result-hash, text flattening, implicit-path
warning). Several aspects drive registration through
``axm_mcp.discovery.register_one`` as a test harness; the subject under test
remains the wrapping behavior.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult

# ---------------------------------------------------------------------------
# --- external step tracing ---
# ---------------------------------------------------------------------------


class TestRegisterOneTracing:
    """register_one integrates tracing for non-protocol tools."""

    def test_non_protocol_tool_calls_trace(self) -> None:
        """AXMTool wrapper calls log_external_step for non-protocol tools."""
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        register_one(mock_mcp, "bib_search", mock_tool)

        # Get the registered wrapper
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper(query="test")
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == "bib_search"

    def test_protocol_tool_skips_trace(self) -> None:
        """Protocol tools (protocol_*) do NOT call log_external_step."""
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()

        def _protocol_fn(**kwargs):
            return {"status": "ok"}

        register_one(mock_mcp, "protocol_init", _protocol_fn)

        # Get the registered wrapper
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper()
            mock_log.assert_not_called()

    def test_plain_fn_calls_trace(self) -> None:
        """Plain function wrapper calls log_external_step."""
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()

        def _my_tool(**kwargs):
            return {"data": "value"}

        register_one(mock_mcp, "ast_context", _my_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper(path="/tmp")
            mock_log.assert_called_once()

    def test_tool_error_still_traces(self) -> None:
        """Tool execution error: tracing still called, tool error propagated."""
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(
            success=False, error="something broke", data={}
        )

        register_one(mock_mcp, "bib_resolve", mock_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            result = wrapper(doi="10.1234/test")
            assert result["success"] is False
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[2] is False  # success=False

    def test_tracing_failure_doesnt_break_tool(self) -> None:
        """If log_external_step raises, tool still returns normally."""
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        register_one(mock_mcp, "bib_search", mock_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch(
            "axm_mcp.wrapping.log_external_step",
            side_effect=RuntimeError("trace broke"),
        ):
            # Tool should still succeed even if tracing fails
            result = wrapper(query="test")
            assert result["success"] is True


# ---------------------------------------------------------------------------
# --- text result wrapping ---
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
    """Register *tool* via ``register_one`` and return the captured wrapper."""
    from axm_mcp.discovery import register_one

    captured: dict[str, Any] = {}

    class _FakeMCP:
        def tool(self, *, name: str) -> Callable[[Any], Any]:
            def _decorator(fn: Any) -> Any:
                captured["wrapper"] = fn
                return fn

            return _decorator

    mcp = _FakeMCP()
    register_one(mcp, name, tool, **register_kwargs)
    return captured["wrapper"]


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(
            FakeToolResult(success=True, data={"k": 1}, text="k: 1"),
            "k: 1",
            id="text_when_set",
        ),
        pytest.param(
            FakeToolResult(success=True, data={"k": 1}),
            {"success": True, "k": 1},
            id="dict_when_text_none",
        ),
        pytest.param(
            FakeToolResult(success=True, data={"k": 1}, text=""),
            "",
            id="empty_string_text",
        ),
        pytest.param(
            FakeToolResult(success=False, data={}, error="bad", text="Error: bad"),
            {"success": False, "error": "bad"},
            id="failing_text_flattens",
        ),
    ],
)
@patch("axm_mcp.wrapping.log_external_step")
def test_wrapper_return_shape(
    mock_log: MagicMock, result: FakeToolResult, expected: object
) -> None:
    """_wrapper returns text when ToolResult.text is set, else flattened dict."""
    tool = FakeTool(result)
    wrapper = _capture_wrapper("my_tool", tool)

    out = wrapper()
    assert out == expected
    assert type(out) is type(expected)


@patch("axm_mcp.wrapping.log_external_step")
def test_wrapper_plain_branch_unchanged(mock_log: MagicMock) -> None:
    """Plain dispatcher functions still return dict as before."""

    def plain_fn(**kwargs: Any) -> dict[str, Any]:
        """A plain tool."""
        return {"status": "ok", "val": kwargs.get("x", 0)}

    wrapper = _capture_wrapper("plain_tool", plain_fn)

    out = wrapper(x=42)
    assert isinstance(out, dict)
    assert out == {"status": "ok", "val": 42}


@patch("axm_mcp.wrapping.log_external_step")
def test_wrapper_text_tracing(mock_log: MagicMock) -> None:
    """When text is set and tracing is active, log_external_step receives the text."""
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


@patch("axm_mcp.wrapping.log_external_step")
def test_text_roundtrip_mcp(mock_log: MagicMock) -> None:
    """Register tool with text output, call via FastMCP ToolManager.

    Response should contain TextContent with raw text, no JSON wrapping.
    """
    from mcp.server.fastmcp import FastMCP

    from axm_mcp.discovery import register_one

    mcp = FastMCP("test-text")
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    register_one(mcp, "text_tool", tool)

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


@patch("axm_mcp.wrapping.log_external_step")
@patch("axm_mcp.wrapping._HTTP_MODE", True)
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


# ---------------------------------------------------------------------------
# --- implicit path warning ---
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("http_mode", "call_kwargs", "expected_warns"),
    [
        pytest.param(True, {"path": "."}, True, id="path_warning_http_mode"),
        pytest.param(False, {"path": "."}, False, id="no_warning_stdio_mode"),
        pytest.param(True, {"path": "/some/dir"}, False, id="no_warning_explicit_path"),
        pytest.param(True, {"query": "test"}, False, id="path_none_no_warning"),
    ],
)
def test_implicit_path_warning(
    caplog: pytest.LogCaptureFixture,
    http_mode: bool,
    call_kwargs: dict[str, Any],
    expected_warns: bool,
) -> None:
    """Implicit-path warning fires iff HTTP mode is on and path is '.' (or empty)."""
    from axm_mcp import wrapping
    from axm_mcp.discovery import register_one

    mock_mcp = MagicMock()
    mock_tool = MagicMock()
    mock_tool.execute.return_value = ToolResult(success=True, data={})

    register_one(mock_mcp, "audit", mock_tool)
    wrapper = mock_mcp.tool.return_value.call_args[0][0]

    original = wrapping._HTTP_MODE
    try:
        wrapping._HTTP_MODE = http_mode
        with caplog.at_level(logging.WARNING, logger="axm_mcp.wrapping"):
            wrapper(**call_kwargs)
    finally:
        wrapping._HTTP_MODE = original

    warned = any("implicit path" in r.message.lower() for r in caplog.records)
    assert warned == expected_warns
    if expected_warns:
        assert any("audit" in r.message for r in caplog.records)


class TestPathWarningPlainFunction:
    """Same checks for the plain-function (dispatcher) code path."""

    def test_plain_fn_warns_http_mode(self, caplog: pytest.LogCaptureFixture) -> None:
        """Plain function wrapper also warns on path='.'."""
        from axm_mcp import wrapping
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()

        def _my_tool(**kwargs):
            return {"ok": True}

        register_one(mock_mcp, "ast_context", _my_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.wrapping"):
                wrapper(path=".")
        finally:
            wrapping._HTTP_MODE = original

        assert any("ast_context" in r.message for r in caplog.records)


class TestPathWarningEdgeCases:
    """Edge cases from test specification."""

    @pytest.mark.asyncio
    async def test_empty_string_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Empty string path is treated like '.' — warns in HTTP mode."""
        from axm_mcp import wrapping
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        register_one(mock_mcp, "git_commit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.wrapping"):
                await wrapper(path="")
        finally:
            wrapping._HTTP_MODE = original

        assert any("git_commit" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# --- hardened serialization: exception guard, text short-circuit, collisions ---
# ---------------------------------------------------------------------------


class RaisingTool:
    """AXMTool-like object whose execute() raises."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def execute(self, **kwargs: Any) -> Any:
        """Raise the configured exception."""
        raise self._exc


@patch("axm_mcp.wrapping.log_external_step")
def test_tool_exception_returns_error_dict(mock_log: MagicMock) -> None:
    """AC1: execute() raising returns the flattened AXM error dict, no escape."""
    tool = RaisingTool(ValueError("boom"))
    wrapper = _capture_wrapper("raising_tool", tool)

    out = wrapper()

    assert isinstance(out, dict)
    assert out["success"] is False
    assert "ValueError" in out["error"]
    assert "boom" in out["error"]


@patch("axm_mcp.wrapping.log_external_step")
def test_plain_fn_exception_returns_error_dict(mock_log: MagicMock) -> None:
    """AC1: plain callable raising returns a flattened success=False dict."""

    def _boom(**kwargs: Any) -> dict[str, Any]:
        """A plain tool that explodes."""
        raise RuntimeError("kaboom")

    wrapper = _capture_wrapper("plain_boom", _boom)

    out = wrapper()

    assert isinstance(out, dict)
    assert out["success"] is False
    assert "RuntimeError" in out["error"]
    assert "kaboom" in out["error"]


@patch("axm_mcp.wrapping.log_external_step")
def test_tool_exception_is_traced(mock_log: MagicMock) -> None:
    """AC2: the exception failure path records a trace with success=False."""
    tool = RaisingTool(ValueError("boom"))
    wrapper = _capture_wrapper("raising_traced", tool)

    wrapper()

    mock_log.assert_called_once()
    # Positional: (name, kwargs, success, output_str, duration_ms)
    call_args = mock_log.call_args[0]
    assert call_args[0] == "raising_traced"
    assert call_args[2] is False  # success=False recorded


@patch("axm_mcp.wrapping.log_external_step")
def test_failing_result_with_text_not_shortcircuited(mock_log: MagicMock) -> None:
    """AC3: a failing ToolResult with text falls through to the flattened dict."""
    result = FakeToolResult(success=False, data={}, error="x", text="# md")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("failing_text", tool)

    out = wrapper()

    assert isinstance(out, dict)
    assert out["success"] is False
    assert out["error"] == "x"


@patch("axm_mcp.wrapping.log_external_step")
def test_success_result_with_text_still_shortcircuits(mock_log: MagicMock) -> None:
    """AC3: a succeeding ToolResult with text still short-circuits to bare markdown."""
    result = FakeToolResult(success=True, data={"k": 1}, text="# md")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("success_text", tool)

    out = wrapper()

    assert out == "# md"
    assert isinstance(out, str)


@patch("axm_mcp.wrapping.log_external_step")
def test_flatten_collision_success_key_preserved(mock_log: MagicMock) -> None:
    """AC4: a data 'success' key is namespaced; envelope success wins; warn logged."""
    result = FakeToolResult(success=True, data={"success": "sentinel"})
    tool = FakeTool(result)
    wrapper = _capture_wrapper("collide_success", tool)

    with patch("axm_mcp.wrapping.logger.warning") as mock_warn:
        out = wrapper()

    assert isinstance(out, dict)
    assert out["success"] is True
    assert out["data_success"] == "sentinel"
    mock_warn.assert_called()


@patch("axm_mcp.wrapping.log_external_step")
def test_flatten_collision_error_hint_keys(mock_log: MagicMock) -> None:
    """AC4: data 'error'/'hint' keys are deterministically namespaced, not leaked."""
    result = FakeToolResult(
        success=True, data={"error": "data-err", "hint": "data-hint"}
    )
    tool = FakeTool(result)
    wrapper = _capture_wrapper("collide_error_hint", tool)

    with patch("axm_mcp.wrapping.logger.warning"):
        out = wrapper()

    assert isinstance(out, dict)
    # Envelope error is unset (success result) -> no leaked 'error' key.
    assert "error" not in out
    assert "hint" not in out
    # Data values relocated deterministically, not lost.
    assert out["data_error"] == "data-err"
    assert out["data_hint"] == "data-hint"


@patch("axm_mcp.wrapping.log_external_step")
def test_flatten_no_collision_shape_unchanged(mock_log: MagicMock) -> None:
    """AC4/AC5: with no reserved-key collision the output shape is unchanged."""
    result = FakeToolResult(success=True, data={"k": 1, "v": "x"})
    tool = FakeTool(result)
    wrapper = _capture_wrapper("no_collision", tool)

    out = wrapper()

    assert out == {"success": True, "k": 1, "v": "x"}


class TestSharedFlatten:
    """AXM-2026: a single importable flatten helper is shared by both call sites."""

    def test_shared_flatten_used_by_wrapper(self) -> None:
        """AC1: wrapping exposes the shared flatten helper with reserved-key
        relocation, and the wrapper hot-path produces the same shape.
        """
        from axm_mcp import wrapping

        result = FakeToolResult(
            success=False, error="bad", data={"success": "shadow", "value": 42}
        )
        flat = wrapping.flatten_result(result)

        assert flat["success"] is False
        assert flat["error"] == "bad"
        assert flat["data_success"] == "shadow"
        assert flat["value"] == 42

        # The wrapper hot-path must yield the identical flattened shape.
        with patch("axm_mcp.wrapping.log_external_step"):
            wrapper = _capture_wrapper("shared_flatten", FakeTool(result))
            assert wrapper() == flat

    def test_shared_flatten_success_envelope(self) -> None:
        """AC1: a clean success flattens with success=True and spread data."""
        from axm_mcp import wrapping

        flat = wrapping.flatten_result(FakeToolResult(success=True, data={"value": 7}))

        assert flat["success"] is True
        assert flat["value"] == 7
        assert "error" not in flat


class TestExistingToolsStillWork:
    """Ensure the warning doesn't break normal tool execution."""

    def test_tool_executes_normally_with_explicit_path(self) -> None:
        """Tool with explicit path runs and returns normally."""
        from axm_mcp import wrapping
        from axm_mcp.discovery import register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with patch("axm_mcp.wrapping.log_external_step"):
                result = wrapper(path="/real/project")
        finally:
            wrapping._HTTP_MODE = original

        assert result["success"] is True
        assert result["result"] == "ok"
