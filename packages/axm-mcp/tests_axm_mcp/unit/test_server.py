"""Tests for axm_mcp.server — HTTP transport + health endpoint."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from axm_mcp import server, wrapping
from axm_mcp.server import serve

# The adopted production listening point, restated as a literal: this module
# owns no port constant of its own and imports none.
_PRODUCTION_PORT = 9427

# ──────────────────────── Unit tests ─────────────────────────


class TestServerPortOwnership:
    """The server module decides no listening point of its own."""

    def test_no_port_constant_and_minimal_public_surface(self) -> None:
        """AC2: the duplicated constant is gone and ``__all__`` names exactly
        the health-check route and the server start function.
        """
        assert not hasattr(server, "DEFAULT_PORT")
        assert sorted(server.__all__) == ["health_check", "serve"]


class TestServeCallsMcpRun:
    """AC1: serve() starts a Streamable HTTP server."""

    def test_serve_calls_mcp_run_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """serve() delegates to mcp.run(transport='streamable-http')."""
        monkeypatch.setenv("AXM_PROFILE", "production")
        monkeypatch.delenv("AXM_MCP_PORT", raising=False)
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()
            mock_mcp.run.assert_called_once_with(
                transport="streamable-http",
                host="127.0.0.1",
                port=_PRODUCTION_PORT,
            )

    def test_serve_path_enables_http_mode(
        self, _restore_http_mode: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: the real HTTP serve path sets ``wrapping._HTTP_MODE`` to True.

        Drives ``server.serve`` (reached in production via ``cli.serve``) with
        only ``mcp.run`` mocked. The flag is NOT patched: we assert the wiring
        actually flips it before ``mcp.run`` is entered.
        """
        monkeypatch.setenv("AXM_PROFILE", "production")
        monkeypatch.delenv("AXM_MCP_PORT", raising=False)
        wrapping._HTTP_MODE = False  # start from the stdio default, no patching
        with patch("axm_mcp.server.mcp") as mock_mcp:
            server.serve()
        mock_mcp.run.assert_called_once_with(
            transport="streamable-http", host="127.0.0.1", port=_PRODUCTION_PORT
        )
        assert wrapping._HTTP_MODE is True

    def test_serve_sets_host_and_port(self) -> None:
        """serve() passes the bind address to run().

        mcp 2.x dropped ``settings.host``/``settings.port``; the transport now
        takes them as run() keywords. Asserting on the call is also stricter
        than the old form, which read back attributes the test had itself set
        on the mock and so could not fail.
        """
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve(host="0.0.0.0", port=9999)  # noqa: S104
            mock_mcp.run.assert_called_once_with(
                transport="streamable-http",
                host="0.0.0.0",  # noqa: S104
                port=9999,
            )


def test_shared_mode_requires_armed_session_resolver() -> None:
    """AC1: shared mode fails before binding without a session resolver."""
    with patch("axm_mcp.server.mcp") as mock_mcp:
        with pytest.raises(server.SharedModeNotArmedError):
            server.serve(shared=True)

    mock_mcp.run.assert_not_called()


class TestServeDefaultPort:
    """AC3: the listening point comes from the shared resolution seam."""

    def test_serve_default_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Port defaults to 9427 under the production profile."""
        monkeypatch.setenv("AXM_PROFILE", "production")
        monkeypatch.delenv("AXM_MCP_PORT", raising=False)
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()
            assert mock_mcp.run.call_args.kwargs["port"] == _PRODUCTION_PORT

    def test_dev_profile_binds_resolved_service_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC3: dev profile, nothing set — serve binds service_port('mcp').

        Under a non-production profile the shared seam derives a per-profile
        listening point, so a profile-isolated installation starts with no
        human-supplied port instead of falling back to the adopted 9427.
        """
        from axm_config import service_port

        monkeypatch.setenv("AXM_PROFILE", "dev")
        monkeypatch.delenv("AXM_MCP_PORT", raising=False)

        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()

        assert mock_mcp.run.call_args.kwargs["port"] == service_port("mcp")


class TestServeEnvPort:
    """AC3: AXM_MCP_PORT env var overrides default."""

    def test_serve_env_port(self) -> None:
        """AXM_MCP_PORT env var is used when no explicit port arg."""
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch.dict(os.environ, {"AXM_MCP_PORT": "8000"}),
        ):
            serve()
            assert mock_mcp.run.call_args.kwargs["port"] == 8000

    def test_explicit_port_overrides_env(self) -> None:
        """Explicit port arg takes precedence over env var."""
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch.dict(os.environ, {"AXM_MCP_PORT": "8000"}),
        ):
            serve(port=7777)
            assert mock_mcp.run.call_args.kwargs["port"] == 7777


class _BoomToolManager:
    """Sentinel that fails on any attribute access.

    Patched in as ``mcp._tool_manager`` so the test proves health_check
    never touches the private MCPServer API (AC1).
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


@pytest.fixture
def _restore_server_state(
    _restore_http_mode: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Undo any process state a serve() call records on the server module."""
    monkeypatch.delenv("AXM_MCP_SHARED", raising=False)
    monkeypatch.delenv("AXM_MCP_SERVE_MODE", raising=False)
    snapshot = dict(vars(server))
    yield
    for key in set(vars(server)) - set(snapshot):
        delattr(server, key)
    for key, value in snapshot.items():
        if vars(server).get(key) is not value:
            setattr(server, key, value)


def _fake_mcp() -> MagicMock:
    fake = MagicMock()
    fake.list_tools = AsyncMock(return_value=[MagicMock(), MagicMock()])
    return fake


class TestHealthReportsServeMode:
    """AC1, AC4: /health reports the mode serve() resolved."""

    @pytest.mark.asyncio
    async def test_health_reports_shared_after_shared_serve(
        self, _restore_server_state: None
    ) -> None:
        """AC1: a shared serve makes /health report shared + enforced contracts."""
        fake = _fake_mcp()
        with patch("axm_mcp.server.mcp", fake):
            server.serve(port=8765, shared=True, session_resolver=lambda: None)
            response = await server.health_check(MagicMock())
        fake.run.assert_called_once()
        body = json.loads(response.body)
        assert body["serve_mode"] == "shared"
        assert body["write_contracts_enforced"] is True

    @pytest.mark.asyncio
    async def test_health_reports_dedicated_after_default_serve(
        self, _restore_server_state: None
    ) -> None:
        """AC4: a default serve reports dedicated, unenforced, keys preserved."""
        fake = _fake_mcp()
        with patch("axm_mcp.server.mcp", fake):
            server.serve(port=8765)
            response = await server.health_check(MagicMock())
        body = json.loads(response.body)
        assert body["serve_mode"] == "dedicated"
        assert body["write_contracts_enforced"] is False
        assert body["status"] == "ok"
        assert body["tools_count"] == 2


# ─────────────────────── Functional tests ────────────────


class TestStdioStillWorks:
    """AC5: existing stdio mode is not broken."""

    def test_stdio_still_works(self) -> None:
        """The stdio default entry calls mcp.run() without a transport."""
        from axm_mcp.cli import app

        with (
            patch("axm_mcp.mcp_app.mcp") as mock_mcp,
            pytest.raises(SystemExit, match="0"),
        ):
            app([], exit_on_error=False)
        mock_mcp.run.assert_called_once_with()


# ──────────────────────── Edge cases ─────────────────────────


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

    def test_missing_env_var_uses_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When AXM_MCP_PORT is not set, default 9427 is used."""
        monkeypatch.setenv("AXM_PROFILE", "production")
        monkeypatch.delenv("AXM_MCP_PORT", raising=False)
        with patch("axm_mcp.server.mcp") as mock_mcp:
            serve()
            assert mock_mcp.run.call_args.kwargs["port"] == _PRODUCTION_PORT
