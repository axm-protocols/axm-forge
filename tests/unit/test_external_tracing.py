"""Tests for external tool tracing in the MCP discovery wrapper.

Verifies that non-protocol tool calls invoke log_external_step(),
protocol tools do NOT double-log, and tracing failures never break
tool execution.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from axm.tools.base import ToolResult

# ---------------------------------------------------------------------------
# Unit tests — _log_external_step helper
# ---------------------------------------------------------------------------


class TestLogExternalStepHelper:
    """_log_external_step() routes to orchestrator.log_external_step()."""

    @patch("axm_engine.runtime.orchestrator.get_orchestrator")
    def test_calls_orchestrator(self, mock_get: MagicMock) -> None:
        """Calls log_external_step on the orchestrator singleton."""
        from axm_mcp.discovery import _log_external_step

        mock_orch = MagicMock()
        mock_get.return_value = mock_orch

        _log_external_step("bib_search", {"query": "test"}, True, "result", 50)

        mock_orch.log_external_step.assert_called_once()
        call_kwargs = mock_orch.log_external_step.call_args[1]
        assert call_kwargs["tool_name"] == "bib_search"
        assert call_kwargs["duration_ms"] == 50

    def test_swallows_import_error(self) -> None:
        """No crash when axm-engine is not installed."""
        from axm_mcp.discovery import _log_external_step

        # Patch the import to raise ImportError
        with patch(
            "axm_engine.runtime.orchestrator.get_orchestrator",
            side_effect=ImportError("no axm_engine"),
        ):
            # Should not raise
            _log_external_step("bib_resolve", {"ref": "10.1234"}, True, "{}", 10)

    @patch("axm_engine.runtime.orchestrator.get_orchestrator")
    def test_swallows_runtime_error(self, mock_get: MagicMock) -> None:
        """No crash when orchestrator raises."""
        mock_orch = MagicMock()
        mock_orch.log_external_step.side_effect = RuntimeError("tracer broken")
        mock_get.return_value = mock_orch

        from axm_mcp.discovery import _log_external_step

        # Should not raise
        _log_external_step("git_preflight", {}, True, "{}", 5)


# ---------------------------------------------------------------------------
# Integration tests — _register_one tracing
# ---------------------------------------------------------------------------


class TestRegisterOneTracing:
    """_register_one integrates tracing for non-protocol tools."""

    def test_non_protocol_tool_calls_trace(self) -> None:
        """AXMTool wrapper calls _log_external_step for non-protocol tools."""
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        _register_one(mock_mcp, "bib_search", mock_tool)

        # Get the registered wrapper
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.discovery._log_external_step") as mock_log:
            wrapper(query="test")
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == "bib_search"

    def test_protocol_tool_skips_trace(self) -> None:
        """Protocol tools (protocol_*) do NOT call _log_external_step."""
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()

        def _protocol_fn(**kwargs):
            return {"status": "ok"}

        _register_one(mock_mcp, "protocol_init", _protocol_fn)

        # Get the registered wrapper
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.discovery._log_external_step") as mock_log:
            wrapper()
            mock_log.assert_not_called()

    def test_plain_fn_calls_trace(self) -> None:
        """Plain function wrapper calls _log_external_step."""
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()

        def _my_tool(**kwargs):
            return {"data": "value"}

        _register_one(mock_mcp, "ast_context", _my_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.discovery._log_external_step") as mock_log:
            wrapper(path="/tmp")
            mock_log.assert_called_once()

    def test_tool_error_still_traces(self) -> None:
        """Tool execution error: tracing still called, tool error propagated."""
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(
            success=False, error="something broke", data={}
        )

        _register_one(mock_mcp, "bib_resolve", mock_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch("axm_mcp.discovery._log_external_step") as mock_log:
            result = wrapper(doi="10.1234/test")
            assert result["success"] is False
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[2] is False  # success=False

    def test_tracing_failure_doesnt_break_tool(self) -> None:
        """If _log_external_step raises, tool still returns normally."""
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        _register_one(mock_mcp, "bib_search", mock_tool)

        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        with patch(
            "axm_mcp.discovery._log_external_step",
            side_effect=RuntimeError("trace broke"),
        ):
            # Tool should still succeed even if tracing fails
            result = wrapper(query="test")
            assert result["success"] is True
