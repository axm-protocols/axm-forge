"""Tests for axm_mcp.cli — CLI lifecycle commands."""

from __future__ import annotations

import os
import signal
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest

from axm_mcp import cli, wrapping
from axm_mcp.cli import (
    app,
    is_process_alive,
    stop,
)


@pytest.fixture
def _restore_http_mode() -> Iterator[None]:
    """Save and restore the module-global ``_HTTP_MODE`` around each test.

    The flag is process-global; serving flips it. We snapshot and restore so
    one test's serve path cannot leak ``True`` into another test.
    """
    saved = wrapping._HTTP_MODE
    try:
        yield
    finally:
        wrapping._HTTP_MODE = saved


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

    def test_cli_status_read_timeout_not_running(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """P3: a ReadTimeout (any httpx.HTTPError) reports 'not running', no
        raw traceback.
        """
        with (
            patch(
                "axm_mcp.cli.httpx.get",
                side_effect=httpx.ReadTimeout("slow"),
            ),
            pytest.raises(SystemExit, match="1"),
        ):
            app(["status"], exit_on_error=False)
        assert "not running" in capsys.readouterr().err.lower()

    def test_cli_status_malformed_json_tolerated(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """P3: a 200 with a non-JSON body still reports running (tools '?')."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("no json")

        with patch("axm_mcp.cli.httpx.get", return_value=mock_resp):
            _run_cli(["status"])
        out = capsys.readouterr().out
        assert "running" in out.lower()
        assert "?" in out


class TestDefaultStdio:
    """AC5: no subcommand runs stdio mode."""

    def test_cli_no_subcommand_stdio(self) -> None:
        """Bare axm-mcp delegates to mcp.run() (stdio)."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            _run_cli([])
            mock_mcp.run.assert_called_once_with()

    def test_stdio_path_leaves_http_mode_false(self, _restore_http_mode: None) -> None:
        """AC1: the stdio default entry leaves ``wrapping._HTTP_MODE`` False.

        Stdio is one process per conversation — no cross-session contention — so
        the lock must stay disengaged. Drives the real ``cli`` stdio default with
        ``mcp.run`` mocked; the flag is asserted, never patched.
        """
        wrapping._HTTP_MODE = False
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            _run_cli([])  # bare CLI -> @app.default stdio entry, public surface
        mock_mcp.run.assert_called_once_with()
        assert wrapping._HTTP_MODE is False


class TestCliServeEnablesHttp:
    """The full ``cli.serve`` chain flips the HTTP mode flag."""

    def test_cli_serve_enables_http_mode(self, _restore_http_mode: None) -> None:
        """AC1, AC4: the full ``cli.serve`` chain enables HTTP mode.

        Covers the production chain cli.serve -> server.serve -> mcp.run with
        ``mcp.run`` mocked. PID file side effects are tolerated (real tmp I/O).
        The flag is asserted, never patched.
        """
        wrapping._HTTP_MODE = False
        with (
            patch("axm_mcp.server.mcp") as mock_mcp,
            patch("axm_mcp.cli.read_pid", return_value=None),
            patch("axm_mcp.cli.write_pid"),
            patch("axm_mcp.cli.remove_pid_file"),
        ):
            cli.serve()
        mock_mcp.run.assert_called_once_with(transport="streamable-http")
        assert wrapping._HTTP_MODE is True


class TestServePidTransactional:
    """P0-1: the PID file is transactional (refuse double serve; conditional
    removal so a failed start never deletes a live server's PID file).
    """

    def test_refuses_when_live_server_owns_pid(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A second ``serve`` refuses to start (and never touches the PID file)
        when a live axm-mcp server already owns it.
        """
        with (
            patch("axm_mcp.cli.read_pid", return_value=4321),
            patch("axm_mcp.cli.is_process_alive", return_value=True),
            patch("axm_mcp.cli.is_axm_mcp_process", return_value=True),
            patch("axm_mcp.cli.write_pid") as mock_write,
            patch("axm_mcp.server.mcp") as mock_mcp,
        ):
            with pytest.raises(SystemExit) as exc:
                cli.serve()
        assert exc.value.code == 1
        mock_write.assert_not_called()
        mock_mcp.run.assert_not_called()
        assert "already running" in capsys.readouterr().err

    def test_failed_start_keeps_foreign_pid_file(self) -> None:
        """When ``serve`` fails after another PID took over the file, the
        ``finally`` does NOT remove it (only removes it if it is still ours).
        """
        own = os.getpid()
        with (
            patch("axm_mcp.cli.read_pid", side_effect=[None, own + 1]),
            patch("axm_mcp.cli.write_pid"),
            patch("axm_mcp.cli.remove_pid_file") as mock_remove,
            patch("axm_mcp.server.mcp") as mock_mcp,
        ):
            mock_mcp.run.side_effect = RuntimeError("bind failed")
            with pytest.raises(RuntimeError, match="bind failed"):
                cli.serve()
        mock_remove.assert_not_called()

    def test_clean_start_removes_own_pid_file(self) -> None:
        """A normal serve removes its own PID file on exit."""
        own = os.getpid()
        with (
            patch("axm_mcp.cli.read_pid", side_effect=[None, own]),
            patch("axm_mcp.cli.write_pid"),
            patch("axm_mcp.cli.remove_pid_file") as mock_remove,
            patch("axm_mcp.server.mcp"),
        ):
            cli.serve()
        mock_remove.assert_called_once()


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
