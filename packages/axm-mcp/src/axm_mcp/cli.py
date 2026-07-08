"""AXM MCP CLI — Lifecycle management for the MCP server.

Subcommands:
    serve   Start the Streamable HTTP server.
    status  Check whether the server is running.
    stop    Send SIGTERM to the running server.

Running ``axm-mcp`` with no subcommand preserves backward-compatible
stdio mode.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
import httpx

__all__ = ["app", "main"]

DEFAULT_PORT = 9427

app = cyclopts.App(
    name="axm-mcp",
    help="AXM MCP Server — lifecycle management.",
    version_flags=[],
)

PID_DIR = Path.home() / ".axm"
PID_FILE = PID_DIR / "mcp-server.pid"


def write_pid(pid: int) -> None:
    """Write PID file, creating parent directory if needed."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def read_pid() -> int | None:
    """Read PID from file, returning None if absent or invalid."""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def is_process_alive(pid: int) -> bool:
    """Check whether a process with *pid* is running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


AXM_MCP_MARKER = "axm-mcp"


def is_axm_mcp_process(pid: int) -> bool:
    """Return True only if *pid*'s command line identifies an axm-mcp server.

    Guards against OS PID reuse: an existence probe (:func:`is_process_alive`)
    cannot tell our server apart from an unrelated process that inherited the
    same PID. We inspect the target's command line via ``ps`` (portable to
    macOS and Linux; no ``/proc`` dependency, no ``psutil``) and require the
    ``axm-mcp`` marker. Any failure (process vanished, ``ps`` error, mismatch)
    yields False — we never send SIGTERM on an unconfirmed identity.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["ps", "-p", str(pid), "-o", "command="],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    return AXM_MCP_MARKER in result.stdout


def remove_pid_file() -> None:
    """Remove PID file if it exists."""
    PID_FILE.unlink(missing_ok=True)


@app.command
def serve(
    *,
    host: Annotated[str, cyclopts.Parameter(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(help="Bind port.")] = DEFAULT_PORT,
) -> None:
    """Start the MCP server with Streamable HTTP transport.

    The PID file is transactional: a second ``serve`` refuses to start when a
    live axm-mcp server already owns it (avoids clobbering the survivor's PID
    with a doomed instance that then fails the bind), and the ``finally`` only
    removes the file when it still contains *our* PID — so a failed start does
    not delete the legitimate server's PID file.
    """
    from axm_mcp import server as _server

    existing = read_pid()
    if (
        existing is not None
        and is_process_alive(existing)
        and is_axm_mcp_process(existing)
    ):
        print(  # noqa: T201
            f"Refusing to start: an axm-mcp server is already running "
            f"(PID {existing}). Use 'axm-mcp stop' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    own_pid = os.getpid()
    write_pid(own_pid)
    try:
        _server.serve(host=host, port=port)
    finally:
        if read_pid() == own_pid:
            remove_pid_file()


@app.command
def status(
    *,
    host: Annotated[str, cyclopts.Parameter(help="Server host.")] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(help="Server port.")] = DEFAULT_PORT,
) -> None:
    """Check whether the MCP server is running."""
    url = f"http://{host}:{port}/health"
    try:
        resp = httpx.get(url, timeout=3)
    except httpx.HTTPError as err:
        # Any transport-level failure (connect refused/timeout, read timeout,
        # malformed response) means "not reachable" — never a raw traceback.
        print("Server not running", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from err

    if resp.status_code != httpx.codes.OK:
        print(f"Server responded with status {resp.status_code}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)
    try:
        tools = resp.json().get("tools_count", "?")
    except ValueError:  # non-JSON body (JSONDecodeError subclasses ValueError)
        tools = "?"
    print(f"Server running on {host}:{port} ({tools} tools)")  # noqa: T201


@app.command
def stop() -> None:
    """Stop the running MCP server.

    Before sending SIGTERM, the target PID's identity is verified against the
    ``axm-mcp`` command-line marker. If the PID has been reused by an unrelated
    process (or vanished), the signal is NOT sent: the stale PID file is
    removed and the command exits non-zero.
    """
    pid = read_pid()

    if pid is None:
        print("Server not running (no PID file)", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    if not is_process_alive(pid):
        remove_pid_file()
        print("Server not running (stale PID file cleaned up)", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    if not is_axm_mcp_process(pid):
        remove_pid_file()
        print(  # noqa: T201
            f"Refusing to stop: PID {pid} is not an axm-mcp process "
            "(reused or vanished); stale PID file cleaned up",
            file=sys.stderr,
        )
        raise SystemExit(1)

    os.kill(pid, signal.SIGTERM)
    remove_pid_file()
    print(f"Sent SIGTERM to server (PID {pid})")  # noqa: T201


@app.command
def install(
    *,
    port: Annotated[int, cyclopts.Parameter(help="Server port.")] = DEFAULT_PORT,
    binary: Annotated[
        Path | None,
        cyclopts.Parameter(help="Explicit binary path for the plist."),
    ] = None,
) -> None:
    """Install the MCP server as a launchd service."""
    from axm_mcp import lifecycle

    lifecycle.install(port, binary=binary)


@app.command
def uninstall() -> None:
    """Uninstall the launchd service."""
    from axm_mcp import lifecycle

    lifecycle.uninstall()


@app.default
def _stdio() -> None:
    """Run MCP in stdio mode (backward-compatible default)."""
    from axm_mcp.mcp_app import mcp

    mcp.run()


def main() -> None:
    """Entry point for ``axm-mcp`` command."""
    app()
