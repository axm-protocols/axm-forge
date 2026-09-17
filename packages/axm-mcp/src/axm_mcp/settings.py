"""Runtime settings for the MCP serving process."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from axm_config import get, profile_root, service_port

__all__ = [
    "HEALTH_PATH",
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


def resolve_pid_file() -> Path:
    """Resolve the MCP server PID file for the active profile."""
    root = profile_root()
    if root is not None:
        return root / "mcp-server.pid"
    return Path.home() / ".axm" / "mcp-server.pid"


def resolve_http_port() -> int:
    """Resolve the MCP HTTP port for the active state profile.

    A listening point is a profile-owned resource, so the decision belongs to
    :func:`axm_config.service_port`: it keeps the adopted 9427 under
    production, derives a per-profile port elsewhere, and still honours the
    historical ``AXM_MCP_PORT`` variable through its alias registry. Reading
    that variable here as well would race that precedence instead of
    deferring to it.
    """
    return service_port("mcp")


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
