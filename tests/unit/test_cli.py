"""Tests for axm_mcp.cli — CLI lifecycle commands."""

from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import httpx
import pytest

from axm_mcp.cli import (
    app,
    is_process_alive,
    stop,
)

# ──────────────────────── Helpers ──────────────────────────


def _run_cli(args: list[str]) -> None:
    """Run the CLI app, swallowing the SystemExit(0) that cyclopts raises."""
    with pytest.raises(SystemExit, match="0"):
        app(args, exit_on_error=False)


# ──────────────────────── Unit tests ──────────────────────────


class TestStatusCommand:
    """AC3: status reports whether the server is running."""

    def test_cli_status_running(self, capsys: pytest.CaptureFixture[str]) -> None:
        """status prints info when server responds 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "tools_count": 42}

        with patch("axm_mcp.cli.httpx.get", return_value=mock_resp):
            _run_cli(["status"])

        out = capsys.readouterr().out
        assert "running" in out.lower()
        assert "42" in out

    def test_cli_status_not_running(self, capsys: pytest.CaptureFixture[str]) -> None:
        """status prints 'not running' when connection fails."""
        with (
            patch(
                "axm_mcp.cli.httpx.get",
                side_effect=httpx.ConnectError("refused"),
            ),
            pytest.raises(SystemExit, match="1"),
        ):
            app(["status"], exit_on_error=False)

        err = capsys.readouterr().err
        assert "not running" in err.lower()

    def test_cli_status_bad_response(self, capsys: pytest.CaptureFixture[str]) -> None:
        """status exits 1 on non-200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with (
            patch("axm_mcp.cli.httpx.get", return_value=mock_resp),
            pytest.raises(SystemExit, match="1"),
        ):
            app(["status"], exit_on_error=False)


class TestDefaultStdio:
    """AC5: no subcommand runs stdio mode."""

    def test_cli_no_subcommand_stdio(self) -> None:
        """Bare axm-mcp delegates to mcp.run() (stdio)."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            _run_cli([])
            mock_mcp.run.assert_called_once_with()


# ──────────────────────── PID helpers ──────────────────────────


class TestPidHelpers:
    """Internal PID file management utilities."""

    def test_is_process_alive_self(self) -> None:
        """Current process is alive."""
        assert is_process_alive(os.getpid()) is True

    def test_is_process_alive_dead(self) -> None:
        """Non-existent PID is not alive."""
        assert is_process_alive(999999999) is False


# ──────────────────────── stop command ──────────────────────────


class TestStopCommand:
    """stop verifies process identity before sending SIGTERM."""

    def test_stop_kills_verified_process(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC3: a genuine axm-mcp process is stopped, PID file removed, exit 0."""
        with (
            patch("axm_mcp.cli.read_pid", return_value=4321),
            patch("axm_mcp.cli.is_process_alive", return_value=True),
            patch("axm_mcp.cli.is_axm_mcp_process", return_value=True),
            patch("axm_mcp.cli.os.kill") as mock_kill,
            patch("axm_mcp.cli.remove_pid_file") as mock_remove,
        ):
            stop()

        mock_kill.assert_called_once_with(4321, signal.SIGTERM)
        mock_remove.assert_called_once_with()
        out = capsys.readouterr().out
        assert "4321" in out

    def test_stop_refuses_unverified_pid(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC1, AC2: PID reused by a foreign process is not killed."""
        with (
            patch("axm_mcp.cli.read_pid", return_value=4321),
            patch("axm_mcp.cli.is_process_alive", return_value=True),
            patch("axm_mcp.cli.is_axm_mcp_process", return_value=False),
            patch("axm_mcp.cli.os.kill") as mock_kill,
            patch("axm_mcp.cli.remove_pid_file") as mock_remove,
            pytest.raises(SystemExit) as exc_info,
        ):
            stop()

        assert exc_info.value.code != 0
        mock_kill.assert_not_called()
        mock_remove.assert_called_once_with()
        err = capsys.readouterr().err
        assert err.strip() != ""

    def test_stop_handles_vanished_process(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC2: process gone between liveness and identity check — no SIGTERM."""
        with (
            patch("axm_mcp.cli.read_pid", return_value=4321),
            patch("axm_mcp.cli.is_process_alive", return_value=True),
            patch("axm_mcp.cli.is_axm_mcp_process", return_value=False),
            patch("axm_mcp.cli.os.kill") as mock_kill,
            patch("axm_mcp.cli.remove_pid_file"),
            pytest.raises(SystemExit) as exc_info,
        ):
            stop()

        assert exc_info.value.code != 0
        mock_kill.assert_not_called()
        err = capsys.readouterr().err
        assert err.strip() != ""
