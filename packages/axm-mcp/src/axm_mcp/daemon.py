"""Daemon declaration consumed by the AXM supervisor."""

from __future__ import annotations

import os
from collections.abc import Mapping

from axm_config import current_profile

from axm_mcp.settings import resolve_http_port, resolve_pid_file

__all__ = ["daemon_descriptor"]

_SERVICE_ID = "axm-mcp"


def daemon_descriptor() -> Mapping[str, Mapping[str, object]]:
    """Build the side-effect-free launch descriptor for the active profile."""
    port = resolve_http_port()
    pid_file = resolve_pid_file()
    environment = {"AXM_PROFILE": current_profile()}
    explicit_port = os.environ.get("AXM_MCP_PORT")
    if explicit_port is not None:
        environment["AXM_MCP_PORT"] = explicit_port

    probe = {"kind": "http", "url": f"http://127.0.0.1:{port}"}
    service: dict[str, object] = {
        "argv": ["axm-mcp", "serve", "--port", str(port)],
        "pid_file": str(pid_file),
        "log_file": str(pid_file.with_name("mcp-server.log")),
        "probe": probe,
        "environment": environment,
    }
    return {_SERVICE_ID: service}
