"""Integration tests for the axm_mcp.cli ``app`` — serve/stop commands.

Black-box CLI behavior driven through the cyclopts ``app`` entry point with
real PID-file / filesystem I/O. PID-helper round-trips live in
``test_read_pid__write_pid.py``.
"""

from __future__ import annotations

import signal
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_mcp.cli import app

pytestmark = pytest.mark.integration

# The CLI's default bind port (axm_mcp.cli.DEFAULT_PORT). Asserted as a literal
# so these command tests reference only the ``app`` entry point.
_DEFAULT_PORT = 9427


@pytest.fixture
def tmp_pid_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Redirect PID file to a temp directory."""
    pid_file = tmp_path / "mcp-server.pid"
    with (
        patch("axm_mcp.cli.PID_DIR", tmp_path),
        patch("axm_mcp.cli.PID_FILE", pid_file),
    ):
        yield pid_file


def _serve_ok(args: list[str]) -> None:
    """Invoke ``app`` for a serve run, swallowing the SystemExit(0) cyclopts raises."""
    with pytest.raises(SystemExit, match="0"):
        app(args, exit_on_error=False)


# ──────────────────────── serve command ──────────────────────────


class TestServeCommand:
    """AC1/AC2: serve subcommand delegates to server.serve."""

    def test_cli_serve_delegates(self, tmp_pid_file: Path) -> None:
        """serve command calls server.serve with default args."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _serve_ok(["serve"])
            mock_serve.assert_called_once_with(host="127.0.0.1", port=_DEFAULT_PORT)

    def test_cli_serve_custom_port(self, tmp_pid_file: Path) -> None:
        """serve --port 8080 passes port to server.serve."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _serve_ok(["serve", "--port", "8080"])
            mock_serve.assert_called_once_with(host="127.0.0.1", port=8080)

    def test_cli_serve_custom_host_port(self, tmp_pid_file: Path) -> None:
        """serve --host 0.0.0.0 --port 3000 passes both args."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _serve_ok(["serve", "--host", "0.0.0.0", "--port", "3000"])  # noqa: S104
            mock_serve.assert_called_once_with(host="0.0.0.0", port=3000)  # noqa: S104

    def test_cli_serve_writes_pid(self, tmp_pid_file: Path) -> None:
        """serve writes the running PID to the PID file before starting."""
        pids_seen: list[str] = []

        def capture_pid(**_kwargs: object) -> None:
            pids_seen.append(tmp_pid_file.read_text())

        with patch("axm_mcp.server.serve", side_effect=capture_pid):
            _serve_ok(["serve"])

        import os

        assert pids_seen == [str(os.getpid())]

    def test_cli_serve_cleans_pid_on_exit(self, tmp_pid_file: Path) -> None:
        """serve removes PID file after server stops."""
        with patch("axm_mcp.server.serve"):
            _serve_ok(["serve"])

        assert not tmp_pid_file.exists()

    def test_cli_serve_cleans_pid_on_error(self, tmp_pid_file: Path) -> None:
        """serve removes PID file even if server raises."""
        with (
            patch("axm_mcp.server.serve", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            app(["serve"], exit_on_error=False)

        assert not tmp_pid_file.exists()


# ──────────────────────── stop command ──────────────────────────


class TestStopCommand:
    """AC4: stop sends SIGTERM to the running server."""

    def test_cli_stop_sends_sigterm(self, tmp_pid_file: Path) -> None:
        """stop reads PID file and sends SIGTERM."""
        tmp_pid_file.write_text("12345")

        with (
            patch("axm_mcp.cli.is_process_alive", return_value=True),
            patch("axm_mcp.cli.os.kill") as mock_kill,
            pytest.raises(SystemExit, match="0"),
        ):
            app(["stop"], exit_on_error=False)

        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        assert not tmp_pid_file.exists()

    def test_cli_stop_no_pid_file(
        self, tmp_pid_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """stop exits 1 when no PID file exists."""
        with pytest.raises(SystemExit, match="1"):
            app(["stop"], exit_on_error=False)

        err = capsys.readouterr().err
        assert "not running" in err.lower()

    def test_cli_stop_stale_pid(
        self, tmp_pid_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """stop cleans up stale PID file when process is dead."""
        tmp_pid_file.write_text("99999")

        with (
            patch("axm_mcp.cli.is_process_alive", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            app(["stop"], exit_on_error=False)

        assert not tmp_pid_file.exists()
        err = capsys.readouterr().err
        assert "stale" in err.lower()
