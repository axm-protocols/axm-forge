"""Launchd lifecycle management for the AXM MCP server."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from axm_mcp.cli import DEFAULT_PORT
from axm_mcp.plist_template import PLIST_TEMPLATE

__all__ = ["find_binary", "generate_plist", "install", "uninstall"]

SERVICE_LABEL = "io.axm.mcp-server"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / "axm-mcp"


def find_binary() -> Path:
    """Locate the ``axm-mcp`` binary on PATH."""
    path = shutil.which("axm-mcp")
    if path is None:
        print("axm-mcp binary not found on PATH", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)
    return Path(path)


def generate_plist(port: int = DEFAULT_PORT) -> str:
    """Render the launchd plist with the current binary path."""
    bin_path = find_binary()
    return PLIST_TEMPLATE.format(
        bin_path=bin_path,
        port=port,
        log_dir=LOG_DIR,
    )


def install(port: int = DEFAULT_PORT) -> None:
    """Generate the plist, write it, and load it via launchctl."""
    plist_content = generate_plist(port)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_content)

    uid = os.getuid()
    launchctl = shutil.which("launchctl") or "launchctl"
    try:
        subprocess.run(  # noqa: S603
            [launchctl, "bootstrap", f"gui/{uid}", str(PLIST_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to load service: {exc.stderr.strip()}", file=sys.stderr)  # noqa: T201
        raise SystemExit(1) from exc

    print(f"Service installed and loaded (port {port})")  # noqa: T201


def uninstall() -> None:
    """Stop the service and remove the plist."""
    if not PLIST_PATH.exists():
        print("Service not installed", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)

    uid = os.getuid()
    launchctl = shutil.which("launchctl") or "launchctl"
    try:
        subprocess.run(  # noqa: S603
            [launchctl, "bootout", f"gui/{uid}", str(PLIST_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        pass  # Service may already be stopped

    PLIST_PATH.unlink(missing_ok=True)
    print("Service uninstalled")  # noqa: T201
