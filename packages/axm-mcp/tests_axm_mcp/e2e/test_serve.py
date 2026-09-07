"""E2E: a second ``axm-mcp serve`` is refused while the first daemon is alive."""

from __future__ import annotations

import subprocess
import time
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


def _shared_mode_process(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> tuple[subprocess.Popen[str], dict[str, str], Path]:
    """Start a shared-mode server with configuration isolated under tmp_path."""
    config_home = tmp_path / ".axm"
    config_home.mkdir(parents=True, exist_ok=True)
    (config_home / "config.toml").write_text(
        '[mcp]\nserve_mode = "shared"\n',
        encoding="utf-8",
    )
    env = sandbox_env(tmp_path)
    env["AXM_HOME"] = str(config_home)
    env.pop("AXM_MCP_SERVE_MODE", None)
    stderr_path = tmp_path / "shared-serve.stderr"
    stderr_stream = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603
        [cli_binary, "serve", "--host", "127.0.0.1", "--port", str(free_port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_stream,
        text=True,
        env=env,
    )
    stderr_stream.close()
    return process, env, stderr_path


def _wait_for_status(
    cli_binary: str,
    free_port: int,
    env: dict[str, str],
    process: subprocess.Popen[str],
) -> subprocess.CompletedProcess[str]:
    """Poll the public status command until the server responds or serve exits."""
    deadline = time.monotonic() + 10
    while True:
        result = subprocess.run(  # noqa: S603
            [
                cli_binary,
                "status",
                "--host",
                "127.0.0.1",
                "--port",
                str(free_port),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 or process.poll() is not None:
            return result
        if time.monotonic() >= deadline:
            return result
        time.sleep(0.05)


def _stop_server(
    cli_binary: str,
    env: dict[str, str],
    process: subprocess.Popen[str],
) -> None:
    """Stop through the public CLI, with a subprocess fallback for failed starts."""
    subprocess.run(  # noqa: S603
        [cli_binary, "stop"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@pytest.mark.e2e
def test_shared_config_serve_is_reported_running(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC1: configured shared serve starts and status reports it running."""
    process, env, _stderr_path = _shared_mode_process(
        tmp_path,
        cli_binary,
        free_port,
        sandbox_env,
    )
    try:
        status_result = _wait_for_status(cli_binary, free_port, env, process)
        assert status_result.returncode == 0
        assert "server running" in status_result.stdout.lower()
    finally:
        _stop_server(cli_binary, env, process)


@pytest.mark.e2e
def test_shared_config_serve_emits_no_arming_or_stdio_refusal(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """AC2: configured shared serve emits neither shared-mode refusal."""
    process, env, stderr_path = _shared_mode_process(
        tmp_path,
        cli_binary,
        free_port,
        sandbox_env,
    )
    try:
        _wait_for_status(cli_binary, free_port, env, process)
        stderr = stderr_path.read_text(encoding="utf-8").lower()
        normalized_stderr = stderr.replace("-", " ")
        assert process.poll() is None, stderr
        assert "sharedmodenotarmederror" not in stderr
        assert "session identity" not in normalized_stderr
        assert not ("stdio" in stderr and "shared mode" in stderr)
    finally:
        _stop_server(cli_binary, env, process)
