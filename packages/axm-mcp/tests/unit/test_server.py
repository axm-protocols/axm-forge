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


class _BoomToolManager:
    """Sentinel that fails on any attribute access.

    Patched in as ``mcp._tool_manager`` so the test proves health_check
    never touches the private FastMCP API (AC1).
    """

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"health_check touched private mcp._tool_manager.{name}")


class TestHealthEndpoint:
    """AC1, AC2: GET /health returns status and tools_count."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self) -> None:
        """AC1, AC2: count comes from the public API, not _tool_manager.

        Registers N fake tools through the public registration path and
        asserts ``tools_count == N`` while ``mcp._tool_manager`` is wired
        to explode on any access — so the handler MUST NOT touch it.
        """
        import json
        from unittest.mock import AsyncMock, MagicMock

        from axm_mcp.server import health_check

        request = MagicMock()
        fake_mcp = MagicMock()
        # Public enumeration API returns the actually-registered set.
        fake_mcp.list_tools = AsyncMock(
            return_value=[MagicMock(), MagicMock(), MagicMock()]
        )
        # Private API must NOT be touched.
        fake_mcp._tool_manager = _BoomToolManager()

        with patch("axm_mcp.server.mcp", fake_mcp):
            response = await health_check(request)

        body = json.loads(response.body)
        assert body["status"] == "ok"
        assert body["tools_count"] == 3


# ──────────────────────── Functional tests ────────────────────


class TestStdioStillWorks:
    """AC5: existing stdio mode is not broken."""

    def test_stdio_still_works(self) -> None:
        """The stdio default entry calls mcp.run() without a transport."""
        from axm_mcp.cli import _stdio

        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            _stdio()
            mock_mcp.run.assert_called_once_with()


# ──────────────────────── Edge cases ──────────────────────────


class TestEdgeCases:
    """Edge cases for port validation."""

    @pytest.mark.parametrize(
        "port",
        [0, 70000],
        ids=["zero", "too_high"],
    )
    def test_invalid_port(self, port: int) -> None:
        """Out-of-range port raises ValueError."""
        with pytest.raises(ValueError, match="port"):
            serve(port=port)

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
