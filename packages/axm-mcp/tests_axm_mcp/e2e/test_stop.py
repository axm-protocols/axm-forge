"""E2E: ``axm-mcp stop`` tears down a running daemon and clears its PID file."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_stop(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
    serve_daemon: Callable[[Path, int], subprocess.Popen[str]],
) -> None:
    """``stop`` exits 0, the daemon terminates, and the PID file is removed.

    Black-box lifecycle: spawn a sandboxed daemon, then ``stop`` it via
    subprocess and assert the real exit code, process teardown, and that the
    isolated PID file is gone.
    """
    daemon = serve_daemon(tmp_path, free_port)
    pid_file = tmp_path / ".axm" / "mcp-server.pid"
    assert pid_file.exists()

    result = subprocess.run(  # noqa: S603
        [cli_binary, "stop"],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "sigterm" in result.stdout.lower()
    daemon.wait(timeout=15)  # raises TimeoutExpired if it did not stop
    assert daemon.poll() is not None
    assert not pid_file.exists()
