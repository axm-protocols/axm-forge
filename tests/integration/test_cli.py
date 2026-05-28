"""Integration tests for axm_mcp.cli — real PID-file / filesystem I/O."""

from __future__ import annotations

import os
import signal
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_mcp.cli import (
    _read_pid,
    _remove_pid_file,
    _write_pid,
    app,
)
from axm_mcp.server import DEFAULT_PORT

pytestmark = pytest.mark.integration

# ──────────────────────── Helpers ──────────────────────────


def _run_cli(args: list[str]) -> None:
    """Run the CLI app, swallowing the SystemExit(0) that cyclopts raises."""
    with pytest.raises(SystemExit, match="0"):
        app(args, exit_on_error=False)


@pytest.fixture
def tmp_pid_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Redirect PID file to a temp directory."""
    pid_file = tmp_path / "mcp-server.pid"
    with (
        patch("axm_mcp.cli.PID_DIR", tmp_path),
        patch("axm_mcp.cli.PID_FILE", pid_file),
    ):
        yield pid_file


# ──────────────────────── serve command ──────────────────────────


class TestServeCommand:
    """AC1/AC2: serve subcommand delegates to server.serve."""

    def test_cli_serve_delegates(self, tmp_pid_file: Path) -> None:
        """serve command calls server.serve with default args."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _run_cli(["serve"])
            mock_serve.assert_called_once_with(host="127.0.0.1", port=DEFAULT_PORT)

    def test_cli_serve_custom_port(self, tmp_pid_file: Path) -> None:
        """serve --port 8080 passes port to server.serve."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _run_cli(["serve", "--port", "8080"])
            mock_serve.assert_called_once_with(host="127.0.0.1", port=8080)

    def test_cli_serve_custom_host_port(self, tmp_pid_file: Path) -> None:
        """serve --host 0.0.0.0 --port 3000 passes both args."""
        with patch("axm_mcp.server.serve") as mock_serve:
            _run_cli(["serve", "--host", "0.0.0.0", "--port", "3000"])  # noqa: S104
            mock_serve.assert_called_once_with(host="0.0.0.0", port=3000)  # noqa: S104

    def test_cli_serve_writes_pid(self, tmp_pid_file: Path) -> None:
        """serve writes PID file before starting."""
        pids_seen: list[int | None] = []

        def capture_pid(**_kwargs: object) -> None:
            pids_seen.append(_read_pid())

        with patch("axm_mcp.server.serve", side_effect=capture_pid):
            _run_cli(["serve"])

        assert pids_seen == [os.getpid()]

    def test_cli_serve_cleans_pid_on_exit(self, tmp_pid_file: Path) -> None:
        """serve removes PID file after server stops."""
        with patch("axm_mcp.server.serve"):
            _run_cli(["serve"])

        assert not tmp_pid_file.exists()

    def test_cli_serve_cleans_pid_on_error(self, tmp_pid_file: Path) -> None:
        """serve removes PID file even if server raises."""
        with (
            patch("axm_mcp.server.serve", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            app(["serve"], exit_on_error=False)

        assert not tmp_pid_file.exists()


class TestStopCommand:
    """AC4: stop sends SIGTERM to the running server."""

    def test_cli_stop_sends_sigterm(
        self, tmp_pid_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """stop reads PID file and sends SIGTERM."""
        tmp_pid_file.write_text("12345")

        with (
            patch("axm_mcp.cli._is_process_alive", return_value=True),
            patch("axm_mcp.cli.os.kill") as mock_kill,
        ):
            _run_cli(["stop"])

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
            patch("axm_mcp.cli._is_process_alive", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            app(["stop"], exit_on_error=False)

        assert not tmp_pid_file.exists()
        err = capsys.readouterr().err
        assert "stale" in err.lower()


# ──────────────────────── PID helpers (I/O) ──────────────────────────


class TestPidHelpers:
    """Internal PID file management utilities."""

    def test_write_and_read_pid(self, tmp_pid_file: Path) -> None:
        """Round-trip write/read of PID file."""
        _write_pid(42)
        assert _read_pid() == 42

    def test_read_pid_missing(self, tmp_pid_file: Path) -> None:
        """read_pid returns None when file is absent."""
        assert _read_pid() is None

    def test_read_pid_corrupt(self, tmp_pid_file: Path) -> None:
        """read_pid returns None when file has non-integer content."""
        tmp_pid_file.write_text("not-a-pid")
        assert _read_pid() is None

    def test_remove_pid_idempotent(self, tmp_pid_file: Path) -> None:
        """remove_pid_file is safe to call when file doesn't exist."""
        _remove_pid_file()  # should not raise
