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


def remove_pid_file() -> None:
    """Remove PID file if it exists."""
    PID_FILE.unlink(missing_ok=True)


@app.command
def serve(
    *,
    host: Annotated[str, cyclopts.Parameter(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(help="Bind port.")] = DEFAULT_PORT,
) -> None:
    """Start the MCP server with Streamable HTTP transport."""
    from axm_mcp import server as _server

    write_pid(os.getpid())
    try:
        _server.serve(host=host, port=port)
    finally:
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
        if resp.status_code == httpx.codes.OK:
            data = resp.json()
            tools = data.get("tools_count", "?")
            print(f"Server running on {host}:{port} ({tools} tools)")  # noqa: T201
        else:
            print(f"Server responded with status {resp.status_code}", file=sys.stderr)  # noqa: T201
            raise SystemExit(1)
    except (httpx.ConnectError, httpx.ConnectTimeout) as err:
        print("Server not running", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from err


@app.command
def stop(
    *,
    host: Annotated[str, cyclopts.Parameter(help="Server host.")] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(help="Server port.")] = DEFAULT_PORT,
) -> None:
    """Stop the running MCP server."""
    pid = read_pid()

    if pid is None:
        print("Server not running (no PID file)", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    if not is_process_alive(pid):
        remove_pid_file()
        print("Server not running (stale PID file cleaned up)", file=sys.stderr)  # noqa: T201
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
