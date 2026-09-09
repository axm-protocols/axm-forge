"""Tests for the MCP tool-call wrapper runtime (axm_mcp.wrapping).

Merged from four aspect-split source files, all dominantly covering
``axm_mcp.wrapping`` (tracing, result-hash, text flattening, implicit-path
warning). The synchronous wrapper (kwarg-unwrap, implicit-path warning,
tracing, exception flattening, text short-circuit) is the direct subject
under test — obtained via :func:`axm_mcp.wrapping.build_wrappers`, the single
construction seam. The async wrapper (HTTP ``to_thread`` offload + per-key
lock) is exercised separately with ``await``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult
from axm.tools.write_scope import WriteContract, decide_write_access

from axm_mcp.session_contracts import SessionContractRegistry
from axm_mcp.wrapping import build_wrappers


def _sync_wrapper(name: str, tool: Any) -> Any:
    """Return the synchronous wrapper for *tool* (the trace/flatten seam)."""
    return build_wrappers(name, tool)[0]


# ---------------------------------------------------------------------------
# --- external step tracing ---
# ---------------------------------------------------------------------------


class TestRegisterOneTracing:
    """register_one integrates tracing for non-protocol tools."""

    def test_non_protocol_tool_calls_trace(self) -> None:
        """AXMTool wrapper calls log_external_step for non-protocol tools."""
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        wrapper = _sync_wrapper("bib_search", mock_tool)

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper(query="test")
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == "bib_search"

    def test_protocol_tool_skips_trace(self) -> None:
        """Protocol tools (protocol_*) do NOT call log_external_step."""

        def _protocol_fn(**kwargs):
            return {"status": "ok"}

        wrapper = _sync_wrapper("protocol_init", _protocol_fn)

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper()
            mock_log.assert_not_called()

    def test_plain_fn_calls_trace(self) -> None:
        """Plain function wrapper calls log_external_step."""

        def _my_tool(**kwargs):
            return {"data": "value"}

        wrapper = _sync_wrapper("ast_context", _my_tool)

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            wrapper(path="/tmp")
            mock_log.assert_called_once()

    def test_tool_error_still_traces(self) -> None:
        """Tool execution error: tracing still called, tool error propagated."""
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(
            success=False, error="something broke", data={}
        )

        wrapper = _sync_wrapper("bib_resolve", mock_tool)

        with patch("axm_mcp.wrapping.log_external_step") as mock_log:
            result = wrapper(doi="10.1234/test")
            assert result["success"] is False
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[2] is False  # success=False

    def test_tracing_failure_doesnt_break_tool(self) -> None:
        """If log_external_step raises, tool still returns normally."""
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        wrapper = _sync_wrapper("bib_search", mock_tool)

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


def _capture_wrapper(name: str, tool: Any) -> Any:
    """Return the synchronous wrapper for *tool* (trace/flatten/short-circuit)."""
    return build_wrappers(name, tool)[0]


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
            "Error: bad",
            id="failing_text_owning_its_error_is_not_doubled",
        ),
        pytest.param(
            FakeToolResult(success=False, data={"k": 1}, error="bad"),
            {"success": False, "k": 1, "error": "bad"},
            id="failing_without_text_flattens",
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


def test_write_contract_denies_out_of_scope_direct_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """The common direct wrapper refuses a batch target outside its prefix."""
    import json

    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": [str(tmp_path / "src")],
            }
        ),
    )
    wrapper = _capture_wrapper(
        "batch_edit",
        FakeTool(FakeToolResult(success=True, text="executed")),
    )

    result = wrapper(
        path=str(tmp_path),
        operations=[{"op": "create", "file": "docs/out.py", "content": ""}],
    )

    assert isinstance(result, dict)
    assert result["success"] is False
    assert "docs/out.py" in str(result["error"])


def test_write_contract_allows_in_scope_direct_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """The same wrapper still executes a batch wholly inside its prefix."""
    import json

    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": [str(tmp_path / "src")],
            }
        ),
    )
    wrapper = _capture_wrapper(
        "batch_edit",
        FakeTool(FakeToolResult(success=True, text="executed")),
    )

    result = wrapper(
        path=str(tmp_path),
        operations=[{"op": "create", "file": "src/in.py", "content": ""}],
    )

    assert result == "executed"


def test_write_contract_denies_out_of_scope_facade_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """ToolCatalog, and therefore axm_call, uses the same scoped wrapper."""
    import json

    from axm_mcp.facade.catalog import ToolCatalog

    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(tmp_path),
                "allowed_prefixes": [str(tmp_path / "src")],
            }
        ),
    )
    tools: dict[str, Any] = {
        "batch_edit": FakeTool(FakeToolResult(success=True, text="executed"))
    }
    catalog = ToolCatalog(tools)

    result = catalog.call(
        "batch_edit",
        {
            "path": str(tmp_path),
            "operations": [{"op": "create", "file": "docs/out.py", "content": ""}],
        },
    )

    assert "success: False" in result
    assert "docs/out.py" in result


def test_malformed_write_contract_fails_wrapper_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed transported contract fails closed before serving tools."""
    monkeypatch.setenv("AXM_WRITE_CONTRACT", "{not-json")

    with pytest.raises(ValueError, match="AXM_WRITE_CONTRACT"):
        _capture_wrapper(
            "batch_edit",
            FakeTool(FakeToolResult(success=True, text="executed")),
        )


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
    """Register tool with text output, call via MCPServer ToolManager.

    Response should contain TextContent with raw text, no JSON wrapping.
    """
    from mcp.server.mcpserver import MCPServer

    from axm_mcp.discovery import register_one

    mcp = MCPServer("test-text")
    result = FakeToolResult(success=True, data={"k": 1}, text="k: 1")
    tool = FakeTool(result)
    register_one(mcp, "text_tool", tool)

    async def _run() -> Any:
        result = await mcp.call_tool("text_tool", {})
        return result.content

    content_list = asyncio.run(_run())
    # MCPServer converts str return → TextContent(text=str), no JSON wrapping
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
    _, wrapper = build_wrappers("protocol_test", tool)

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

    mock_tool = MagicMock()
    mock_tool.execute.return_value = ToolResult(success=True, data={})

    wrapper = _sync_wrapper("audit", mock_tool)

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

        def _my_tool(**kwargs):
            return {"ok": True}

        wrapper = _sync_wrapper("ast_context", _my_tool)

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
def test_failing_result_with_text_prefixed_with_status(mock_log: MagicMock) -> None:
    """A failing ToolResult keeps its own text, behind a composed status line.

    The text a tool renders for its failure paths is the diagnostic the reader
    needs most; it reaches them, while the leading marker and the ``error``
    keep the failure unmistakable.
    """
    result = FakeToolResult(success=False, data={}, error="x", text="# md")
    tool = FakeTool(result)
    wrapper = _capture_wrapper("failing_text", tool)

    out = wrapper()

    assert isinstance(out, str)
    assert out == "✗ x\n# md"


@patch("axm_mcp.wrapping.log_external_step")
def test_failing_text_quoting_error_later_still_marked(mock_log: MagicMock) -> None:
    """An error echoed further down the text does not suppress the marker.

    Only a first line already carrying the error counts as the tool's own
    status header. An error string quoted inside a diagnostic body (or an
    anchor excerpt) must not be enough to strip the marker, or a failure could
    arrive looking unmarked.
    """
    result = FakeToolResult(
        success=False, data={}, error="boom", text="header\n  detail: boom here"
    )
    wrapper = _capture_wrapper("late_echo", FakeTool(result))

    out = wrapper()

    assert out.startswith("✗ boom")


@patch("axm_mcp.wrapping.log_external_step")
def test_failing_result_cannot_masquerade_as_success(mock_log: MagicMock) -> None:
    """A failing tool cannot present itself as passing, whatever its text says.

    Guards the invariant behind the original success-gated short-circuit: a
    ``ToolResult(success=False)`` must never reach the reader as bare prose.
    The gate bought that by discarding the text; the status line composed by
    the wrapper buys it without the loss. Do not re-gate the shortcut on
    ``success`` to restore this property - this test already holds it.
    """
    result = FakeToolResult(
        success=False, data={}, error="disk full", text="everything is fine"
    )
    wrapper = _capture_wrapper("masquerade", FakeTool(result))

    out = wrapper()

    assert isinstance(out, str)
    assert out.startswith("\u2717 disk full")
    assert "everything is fine" in out


@patch("axm_mcp.wrapping.log_external_step")
def test_failing_result_without_text_still_flattens(mock_log: MagicMock) -> None:
    """A failure carrying no text keeps the structured envelope as its fallback."""
    result = FakeToolResult(success=False, data={"detail": 1}, error="x")
    wrapper = _capture_wrapper("failing_no_text", FakeTool(result))

    out = wrapper()

    assert isinstance(out, dict)
    assert out["success"] is False
    assert out["error"] == "x"
    assert out["detail"] == 1


@patch("axm_mcp.wrapping.log_external_step")
def test_failing_result_text_carries_hint(mock_log: MagicMock) -> None:
    """``hint`` survives the text path, as it does on the flattened one."""
    result = FakeToolResult(
        success=False, data={}, error="bad anchor", text="details", hint="re-read it"
    )
    wrapper = _capture_wrapper("failing_hint", FakeTool(result))

    out = wrapper()

    assert out == "\u2717 bad anchor\ndetails\nhint: re-read it"


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

    @pytest.mark.asyncio
    async def test_tool_executes_normally_with_explicit_path(self) -> None:
        """A non-locked tool runs via to_thread in HTTP mode and returns normally."""
        from axm_mcp import wrapping

        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        # audit has no git_/protocol_ prefix → no lock, but HTTP mode still
        # offloads the sync body to a worker thread (P1-2): the event loop is
        # never blocked by a sync tool.
        _, wrapper = build_wrappers("audit", mock_tool)

        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with patch("axm_mcp.wrapping.log_external_step"):
                result = await wrapper(path="/real/project")
        finally:
            wrapping._HTTP_MODE = original

        assert result["success"] is True
        assert result["result"] == "ok"


class TestHttpLockBehavior:
    """P1-2/P1-3/P2-2 — HTTP-mode locking on the async wrapper."""

    @pytest.mark.asyncio
    async def test_lock_timeout_is_flattened(self) -> None:
        """P1-3: a lock-acquire timeout becomes the AXM error envelope, not a
        raw ``TimeoutError`` propagated to MCPServer.
        """
        from collections.abc import AsyncIterator
        from contextlib import asynccontextmanager

        from axm_mcp import wrapping

        tool = FakeTool(FakeToolResult(success=True, data={"ok": 1}, text="ok"))

        @asynccontextmanager
        async def _always_times_out(_key: str) -> AsyncIterator[None]:
            raise TimeoutError
            yield  # pragma: no cover

        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            # Patch BEFORE building: the wrapper captures the lock at build time.
            with patch.object(wrapping, "_git_lock", _always_times_out):
                _, wrapper = build_wrappers("git_commit", tool)
                out = await wrapper(path="/repo")
        finally:
            wrapping._HTTP_MODE = original

        assert isinstance(out, dict)
        assert out["success"] is False
        assert "busy" in str(out["error"])

    @pytest.mark.asyncio
    async def test_equivalent_paths_share_one_lock(self) -> None:
        """P2-2: '/repo' and '/repo/' normalise to the same lock key, so two
        concurrent calls on the equivalent paths serialize.
        """
        from axm_mcp import wrapping

        order: list[str] = []

        class _Slow:
            def execute(self, *, path: str = "", **_kwargs: Any) -> Any:
                import time

                order.append("start")
                time.sleep(0.05)
                order.append("end")
                return ToolResult(success=True, data={}, text="ok")

        _, wrapper = build_wrappers("git_commit", _Slow())
        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with patch("axm_mcp.wrapping.log_external_step"):
                await asyncio.gather(
                    wrapper(path="/repo"),
                    wrapper(path="/repo/"),
                )
        finally:
            wrapping._HTTP_MODE = original

        # Serialized despite the trailing-slash difference.
        assert order == ["start", "end", "start", "end"]

    @pytest.mark.asyncio
    async def test_non_string_key_does_not_crash(self) -> None:
        """P3: a non-string ``path`` skips the lock rather than raising
        ``AssertionError`` — the tool still runs.
        """
        from axm_mcp import wrapping

        tool = FakeTool(FakeToolResult(success=True, data={"ok": 1}, text="ok"))
        _, wrapper = build_wrappers("git_commit", tool)
        original = wrapping._HTTP_MODE
        try:
            wrapping._HTTP_MODE = True
            with patch("axm_mcp.wrapping.log_external_step"):
                out = await wrapper(path=12345)
        finally:
            wrapping._HTTP_MODE = original
        assert out == "ok"


def _contract(root: str, prefix: str) -> WriteContract:
    return WriteContract.from_mapping(
        {"execution_root": root, "allowed_prefixes": [prefix]}
    )


def _shared_wrapper(
    recorder: Any,
    registry: SessionContractRegistry,
    current_session: dict[str, str],
) -> Any:
    return build_wrappers(
        "batch_edit",
        recorder,
        shared_mode=True,
        write_contract_resolver=lambda: registry.resolve(current_session["id"]),
    )[0]


def test_shared_wrapper_resolves_contract_for_each_emitting_session() -> None:
    """AC1: one wrapper set resolves the perimeter of every emitting session."""
    calls: list[dict[str, object]] = []

    def recorder(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"success": True}

    registry = SessionContractRegistry(clock=lambda: 0.0)
    registry.bind("s-a", _contract("/workspace", "/workspace/a"))
    registry.bind("s-b", _contract("/workspace", "/workspace/b"))
    current_session = {"id": "s-a"}
    wrapper = _shared_wrapper(recorder, registry, current_session)
    request = {
        "path": "/workspace/b",
        "operations": [{"op": "create", "file": "out.txt", "content": "session-b"}],
    }

    refused = wrapper(**request)

    assert isinstance(refused, dict)
    assert refused["success"] is False
    assert calls == []

    current_session["id"] = "s-b"
    allowed = wrapper(**request)

    assert allowed == {"success": True}
    assert calls == [request]


def test_shared_wrapper_refuses_unbound_session() -> None:
    """AC2: shared mode refuses a session with no attached perimeter."""
    calls: list[dict[str, object]] = []

    def recorder(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"success": True}

    registry = SessionContractRegistry(clock=lambda: 0.0)
    current_session = {"id": "s-ghost"}
    wrapper = _shared_wrapper(recorder, registry, current_session)

    result = wrapper(
        path="/workspace",
        operations=[{"op": "create", "file": "out.txt", "content": "blocked"}],
    )

    assert isinstance(result, dict)
    assert result["success"] is False
    assert (
        "refus" in str(result["error"]).lower()
        or "no write contract" in str(result["error"]).lower()
    )
    assert calls == []


def test_shared_wrapper_refuses_when_resolver_returns_no_contract() -> None:
    """AC2: shared mode refuses on a resolver that yields None without raising.

    The registry-backed resolver raises for an unknown session, so every other
    shared-mode test is refused *before* the reversal is consulted. This one
    exercises the reversal itself: a resolver that legitimately reports "no
    perimeter" by returning None must still be refused, because in shared mode
    the absence of a contract means denial, not permission.
    """
    calls: list[dict[str, object]] = []

    def recorder(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"success": True}

    wrapper = build_wrappers(
        "batch_edit",
        recorder,
        shared_mode=True,
        write_contract_resolver=lambda: None,
    )[0]

    result = wrapper(
        path="/workspace",
        operations=[{"op": "create", "file": "out.txt", "content": "blocked"}],
    )

    assert isinstance(result, dict)
    assert result["success"] is False
    assert "no write contract" in str(result["error"]).lower()
    assert calls == []


def test_shared_wrapper_refusal_warns_with_session_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC3: an unbound-session refusal logs its session id at WARNING."""
    registry = SessionContractRegistry(clock=lambda: 0.0)
    current_session = {"id": "s-ghost"}
    wrapper = _shared_wrapper(
        lambda **_kwargs: {"success": True}, registry, current_session
    )

    with caplog.at_level(logging.WARNING, logger="axm_mcp.wrapping"):
        wrapper(
            path="/workspace",
            operations=[{"op": "create", "file": "out.txt", "content": "blocked"}],
        )

    warnings = [
        record
        for record in caplog.records
        if record.name == "axm_mcp.wrapping" and record.levelno == logging.WARNING
    ]
    assert warnings
    assert any("s-ghost" in record.getMessage() for record in warnings)


def test_single_client_without_contract_keeps_allow_reason() -> None:
    """AC4: single-client mode keeps the literal no-contract allow decision."""
    calls: list[dict[str, object]] = []
    decisions: list[Any] = []

    def recorder(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"success": True}

    def record_decision(
        contract: object,
        tool_name: str,
        tool_input: dict[str, object],
    ) -> Any:
        decision = decide_write_access(contract, tool_name, tool_input)
        decisions.append(decision)
        return decision

    with patch(
        "axm.tools.write_scope.decide_write_access",
        side_effect=record_decision,
    ):
        wrapper = build_wrappers(
            "batch_edit",
            recorder,
            shared_mode=False,
            write_contract_resolver=lambda: None,
        )[0]
        result = wrapper(
            path="/workspace",
            operations=[{"op": "create", "file": "out.txt", "content": "allowed"}],
        )

    assert result == {"success": True}
    assert len(calls) == 1
    assert len(decisions) == 1
    assert decisions[0].allowed is True
    assert decisions[0].reason == "no write contract is in force"


def _write_lock_keys(name: str, kwargs: dict[str, object]) -> tuple[str, ...]:
    from axm_mcp import wrapping

    selected = wrapping._select_lock(name, kwargs)
    assert selected is not None
    return tuple(selected[1])


def test_write_and_edit_file_use_their_normalized_path_as_lock_key() -> None:
    """AC1: write_file and edit_file lock on their non-empty normalized path."""
    from axm_mcp import wrapping

    path = "/tmp/axm/a.py"
    expected = wrapping._normalize_lock_key(path)
    assert expected is not None

    for tool_name in ("write_file", "edit_file"):
        keys = _write_lock_keys(tool_name, {"path": path})
        assert keys == (expected,)
        assert keys


def test_equivalent_write_file_paths_share_one_lock_key() -> None:
    """AC2: equivalent designations of one file collapse onto one lock key."""
    first = _write_lock_keys(
        "write_file",
        {"path": "/tmp/axm/sub/../a.py"},
    )
    second = _write_lock_keys(
        "write_file",
        {"path": "/tmp/axm/a.py/"},
    )

    assert first == second


def test_distinct_write_file_paths_have_distinct_lock_keys() -> None:
    """AC3: distinct files retain distinct per-file lock keys."""
    first = _write_lock_keys("write_file", {"path": "/tmp/axm/a.py"})
    second = _write_lock_keys("write_file", {"path": "/tmp/axm/b.py"})

    assert first != second


def test_batch_edit_keys_each_operation_file_under_root() -> None:
    """AC4: batch_edit yields sorted normalized keys for every operation file."""
    from axm_mcp import wrapping

    root = "/tmp/axm/repo"
    keys = _write_lock_keys(
        "batch_edit",
        {
            "path": root,
            "operations": [
                {"file": "b.py"},
                {"file": "a.py"},
            ],
        },
    )
    expected = (
        wrapping._normalize_lock_key(f"{root}/a.py"),
        wrapping._normalize_lock_key(f"{root}/b.py"),
    )

    assert all(key is not None for key in expected)
    assert keys == expected
