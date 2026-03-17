"""Tests for implicit-path warnings in HTTP mode.

Verifies that _register_one wrappers log a WARNING when path="." or ""
and _HTTP_MODE is True, and stay silent otherwise.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import ToolResult

# ---------------------------------------------------------------------------
# Unit tests — _warn_implicit_path via _register_one wrappers
# ---------------------------------------------------------------------------


class TestPathWarningHTTPMode:
    """Wrapper warns on implicit path when _HTTP_MODE is True."""

    def test_path_warning_http_mode(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warning logged when path='.' and HTTP mode is on."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        _register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                wrapper(path=".")
        finally:
            discovery._HTTP_MODE = original

        assert any(
            "audit" in r.message and "implicit path" in r.message.lower()
            for r in caplog.records
        )

    def test_no_warning_stdio_mode(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning when _HTTP_MODE is False (stdio transport)."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        _register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = False
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                wrapper(path=".")
        finally:
            discovery._HTTP_MODE = original

        assert not any("implicit path" in r.message.lower() for r in caplog.records)

    def test_no_warning_explicit_path(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning when an explicit absolute path is provided."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        _register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                wrapper(path="/some/dir")
        finally:
            discovery._HTTP_MODE = original

        assert not any("implicit path" in r.message.lower() for r in caplog.records)


class TestPathWarningPlainFunction:
    """Same checks for the plain-function (dispatcher) code path."""

    def test_plain_fn_warns_http_mode(self, caplog: pytest.LogCaptureFixture) -> None:
        """Plain function wrapper also warns on path='.'."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()

        def _my_tool(**kwargs):
            return {"ok": True}

        _register_one(mock_mcp, "ast_context", _my_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                wrapper(path=".")
        finally:
            discovery._HTTP_MODE = original

        assert any("ast_context" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPathWarningEdgeCases:
    """Edge cases from test specification."""

    def test_path_none_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning when path is not passed at all."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        _register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                wrapper(query="test")
        finally:
            discovery._HTTP_MODE = original

        assert not any("implicit path" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_empty_string_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Empty string path is treated like '.' — warns in HTTP mode."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={})

        _register_one(mock_mcp, "git_commit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with caplog.at_level(logging.WARNING, logger="axm_mcp.discovery"):
                await wrapper(path="")
        finally:
            discovery._HTTP_MODE = original

        assert any("git_commit" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Functional / regression
# ---------------------------------------------------------------------------


class TestExistingToolsStillWork:
    """Ensure the warning doesn't break normal tool execution."""

    def test_tool_executes_normally_with_explicit_path(self) -> None:
        """Tool with explicit path runs and returns normally."""
        import axm_mcp.discovery as discovery
        from axm_mcp.discovery import _register_one

        mock_mcp = MagicMock()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = ToolResult(success=True, data={"result": "ok"})

        _register_one(mock_mcp, "audit", mock_tool)
        wrapper = mock_mcp.tool.return_value.call_args[0][0]

        original = discovery._HTTP_MODE
        try:
            discovery._HTTP_MODE = True
            with patch("axm_mcp.discovery._log_external_step"):
                result = wrapper(path="/real/project")
        finally:
            discovery._HTTP_MODE = original

        assert result["success"] is True
        assert result["result"] == "ok"
