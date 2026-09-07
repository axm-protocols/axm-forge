"""Runtime settings for the MCP serving process."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from axm_config import current_profile, get, profile_root

__all__ = [
    "NonProductionPortError",
    "resolve_http_port",
    "resolve_pid_file",
    "resolve_serve_mode",
]

type ServeMode = Literal["shared", "dedicated"]


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
