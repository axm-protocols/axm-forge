"""Runtime settings for the MCP serving process."""

from __future__ import annotations

from typing import Literal

from axm_config import get

__all__ = ["resolve_serve_mode"]

type ServeMode = Literal["shared", "dedicated"]


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
