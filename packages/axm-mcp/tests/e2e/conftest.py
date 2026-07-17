"""Shared fixtures for black-box e2e tests of the axm-mcp CLI.

These tests spawn the real ``axm-mcp`` console-script binary via subprocess
(no mocks, no in-process import of first-party symbols) and drive the PID-file
lifecycle inside a sandboxed ``$HOME`` so they never collide with a real
daemon. The CLI derives its PID file from ``Path.home()/.axm/mcp-server.pid``,
so redirecting ``$HOME`` to ``tmp_path`` fully isolates each run.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_READY_TIMEOUT = 40.0
_POLL_INTERVAL = 0.1


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _pid_file_for(home: Path) -> Path:
    return home / ".axm" / "mcp-server.pid"


def _await_ready(proc: subprocess.Popen[str], pid_file: Path, port: int) -> None:
    deadline = time.monotonic() + _READY_TIMEOUT
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(
                f"serve exited early (code {proc.returncode}); "
                f"stdout={out!r} stderr={err!r}"
            )
        if pid_file.exists() and _port_open(port):
            return
        time.sleep(_POLL_INTERVAL)
    raise AssertionError(f"serve not ready within {_READY_TIMEOUT}s (port {port})")


def _terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


@pytest.fixture
def cli_binary() -> str:
    """Absolute path to the installed ``axm-mcp`` console script."""
    binary = shutil.which("axm-mcp")
    if binary is None:  # pragma: no cover - environment guard
        pytest.skip("axm-mcp console script not found on PATH")
    return binary


@pytest.fixture
def free_port() -> int:
    """An ephemeral TCP port free at fixture time."""
    return _pick_free_port()


@pytest.fixture
def sandbox_env() -> Callable[[Path], dict[str, str]]:
    """Build a subprocess env whose ``$HOME`` redirects the PID file."""

    def _build(home: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["HOME"] = str(home)
        return env

    return _build


@pytest.fixture
def serve_daemon(
    cli_binary: str,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> Iterator[Callable[[Path, int], subprocess.Popen[str]]]:
    """Spawn ``axm-mcp serve`` sandboxed on *home*/*port*, ready to use.

    The returned factory blocks until the server has written its PID file and
    opened its port, so callers observe a fully-live daemon. Every spawned
    process is torn down in ``finally`` regardless of test outcome.
    """
    procs: list[subprocess.Popen[str]] = []

    def _spawn(home: Path, port: int) -> subprocess.Popen[str]:
        proc = subprocess.Popen(  # noqa: S603
            [cli_binary, "serve", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=sandbox_env(home),
        )
        procs.append(proc)
        _await_ready(proc, _pid_file_for(home), port)
        return proc

    try:
        yield _spawn
    finally:
        for proc in procs:
            _terminate(proc)
