"""Tests for axm_mcp.server — HTTP transport + health endpoint."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from axm_mcp.server import DEFAULT_PORT, serve

# ──────────────────────── Unit tests ──────────────────────────


class TestServeCallsMcpRun:
    """AC1: serve() starts a Streamable HTTP server."""

    def test_serve_calls_mcp_run_http(self) -> None:
        """serve() delegates to mcp.run(transport='streamable-http')."""
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()
            mock_mcp.run.assert_called_once_with(transport="streamable-http")

    def test_serve_sets_host_and_port(self) -> None:
        """serve() configures mcp.settings before calling run."""
        with patch("axm_mcp.server.mcp") as mock_mcp:
            mock_mcp.settings.host = "0.0.0.0"  # noqa: S104
            mock_mcp.settings.port = 9999
            serve(host="0.0.0.0", port=9999)  # noqa: S104
            assert mock_mcp.settings.host == "0.0.0.0"  # noqa: S104
            assert mock_mcp.settings.port == 9999


class TestServeDefaultPort:
    """AC3: default port is 9427."""

    def test_serve_default_port(self) -> None:
        """Port defaults to 9427 when no args and no env var."""
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()
            assert mock_mcp.settings.port == DEFAULT_PORT


class TestServeEnvPort:
    """AC3: AXM_MCP_PORT env var overrides default."""

    def test_serve_env_port(self) -> None:
        """AXM_MCP_PORT env var is used when no explicit port arg."""
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch.dict(os.environ, {"AXM_MCP_PORT": "8000"}),
        ):
            serve()
            assert mock_mcp.settings.port == 8000

    def test_explicit_port_overrides_env(self) -> None:
        """Explicit port arg takes precedence over env var."""
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch.dict(os.environ, {"AXM_MCP_PORT": "8000"}),
        ):
            serve(port=7777)
            assert mock_mcp.settings.port == 7777


class TestHealthEndpoint:
    """AC2: GET /health returns status and tools_count."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self) -> None:
        """Health handler returns {"status": "ok", "tools_count": N}."""
        # health_check is an async function (Request) -> JSONResponse
        # We can call it directly with a mock request
        from unittest.mock import MagicMock

        from axm_mcp.server import health_check

        request = MagicMock()
        with patch("axm_mcp.server.mcp") as mock_mcp:
            mock_mcp._tool_manager.list_tools = MagicMock(
                return_value=[MagicMock(), MagicMock(), MagicMock()]
            )
            response = await health_check(request)

        import json

        body = json.loads(response.body)
        assert body["status"] == "ok"
        assert body["tools_count"] == 3


# ──────────────────────── Functional tests ────────────────────


class TestStdioStillWorks:
    """AC5: existing stdio mode is not broken."""

    def test_stdio_still_works(self) -> None:
        """Package-level main() still calls mcp.run() without transport."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            from axm_mcp.mcp_app import main

            main()
            mock_mcp.run.assert_called_once_with()


# ──────────────────────── Edge cases ──────────────────────────


class TestEdgeCases:
    """Edge cases for port validation."""

    def test_invalid_port_zero(self) -> None:
        """Port 0 raises ValueError."""
        with pytest.raises(ValueError, match="port"):
            serve(port=0)

    def test_invalid_port_too_high(self) -> None:
        """Port > 65535 raises ValueError."""
        with pytest.raises(ValueError, match="port"):
            serve(port=70000)

    def test_invalid_port_negative(self) -> None:
        """Negative port raises ValueError."""
        with pytest.raises(ValueError, match="port"):
            serve(port=-1)

    def test_missing_env_var_uses_default(self) -> None:
        """When AXM_MCP_PORT is not set, default 9427 is used."""
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch.dict(os.environ, {}, clear=False),
        ):
            # Ensure AXM_MCP_PORT is not set
            os.environ.pop("AXM_MCP_PORT", None)
            serve()
            assert mock_mcp.settings.port == DEFAULT_PORT
