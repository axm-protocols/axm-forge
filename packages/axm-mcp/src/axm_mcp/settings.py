"""Runtime settings for the MCP serving process."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from axm_config import current_profile, get, profile_root

__all__ = [
    "HEALTH_PATH",
    "NonProductionPortError",
    "health_url",
    "resolve_http_port",
    "resolve_pid_file",
    "resolve_serve_mode",
]

#: Path the server answers a liveness check on. Declared here rather than at the
#: route, because three places must agree on it: the route that serves it, the
#: ``status`` CLI that polls it, and the daemon descriptor that publishes it to
#: the supervisor. They did not: the descriptor advertised the bare origin,
#: which the server answers with 404, so a supervisor probing that URL read a
#: live server as stopped — and its caller then tried to start a second one.
#: A module the others already import, and that imports nothing of its own,
#: keeps the descriptor free of the serving stack it must not pull in.
HEALTH_PATH = "/health"

type ServeMode = Literal["shared", "dedicated"]


def health_url(host: str, port: int) -> str:
    """Build the liveness URL a supervisor or the CLI should poll."""
    return f"http://{host}:{port}{HEALTH_PATH}"


class NonProductionPortError(ValueError):
    """Raised when a non-production profile has no explicit MCP HTTP port."""


def resolve_pid_file() -> Path:
    """Resolve the MCP server PID file for the active profile."""
    root = profile_root()
    if root is not None:
        return root / "mcp-server.pid"
    return Path.home() / ".axm" / "mcp-server.pid"


def resolve_http_port() -> int:
    """Resolve the MCP HTTP port, requiring an override outside production."""
    override = os.environ.get("AXM_MCP_PORT")
    if override is not None:
        return int(override)

    profile = current_profile()
    if profile != "production":
        msg = f"profile {profile!r} requires the AXM_MCP_PORT environment variable"
        raise NonProductionPortError(msg)
    return 9427


def resolve_serve_mode(explicit: str | None = None) -> ServeMode:
    """Resolve serving mode with explicit > environment > file > default."""
    resolved = (
        explicit
        if explicit is not None
        else get("mcp", "serve_mode", default="dedicated")
    )
    match resolved:
        case "shared":
            return "shared"
        case "dedicated":
            return "dedicated"
        case _:
            msg = f"invalid serve mode: {resolved!r}"
            raise ValueError(msg)
