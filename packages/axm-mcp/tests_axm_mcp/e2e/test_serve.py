"""E2E: a second ``axm-mcp serve`` is refused while the first daemon is alive."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_serve(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
    serve_daemon: Callable[[Path, int], subprocess.Popen[str]],
) -> None:
    """Double-start guard: the second ``serve`` exits non-zero, PID file intact.

    Drives the PID-file lifecycle end-to-end over subprocess with real exit
    codes: a live daemon owns the sandboxed PID file, and a second ``serve``
    against the same ``$HOME`` must refuse rather than clobber the survivor.
    """
    first = serve_daemon(tmp_path, free_port)
    pid_file = tmp_path / ".axm" / "mcp-server.pid"
    assert pid_file.read_text().strip() == str(first.pid)

    second = subprocess.run(  # noqa: S603
        [cli_binary, "serve", "--host", "127.0.0.1", "--port", str(free_port)],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=30,
        check=False,
    )

    assert second.returncode != 0
    assert "already running" in second.stderr.lower()
    # The survivor's PID file is untouched -- still points at the first daemon.
    assert pid_file.read_text().strip() == str(first.pid)
    assert first.poll() is None


@pytest.mark.e2e
def test_shared_stdio_is_refused(
    tmp_path: Path,
    cli_binary: str,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC5: stdio cannot arm shared mode without a session identity."""
    result = subprocess.run(  # noqa: S603
        [cli_binary, "serve", "--shared"],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=10,
        check=False,
    )

    assert result.returncode == 1
    assert "shared mode" in result.stderr.lower()


@pytest.mark.e2e
def test_invalid_configured_serve_mode_is_refused(
    tmp_path: Path,
    cli_binary: str,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC6: serve exits 1 and names an invalid environment-configured mode."""
    env = sandbox_env(tmp_path)
    env["AXM_MCP_SERVE_MODE"] = "bogus"

    result = subprocess.run(  # noqa: S603
        [cli_binary, "serve"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )

    assert result.returncode == 1
    assert "bogus" in result.stderr.lower()
    assert "invalid" in result.stderr.lower()
    assert "serve mode" in result.stderr.lower()
