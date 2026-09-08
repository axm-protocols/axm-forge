"""Daemon declaration consumed by the AXM supervisor."""

from __future__ import annotations

import os
from collections.abc import Mapping
from hashlib import blake2s

from axm_config import current_profile

from axm_mcp.settings import resolve_http_port, resolve_pid_file

__all__ = ["daemon_descriptor"]

_SERVICE_ID = "io.axm.mcp"


def _service_id(profile: str) -> str:
    if profile == "production":
        return _SERVICE_ID

    digest = blake2s(profile.encode("utf-8"), digest_size=4).hexdigest()
    stem = "".join(
        character
        for character in profile.lower()
        if character.isascii() and character.isalnum()
    )
    if not stem or not stem[0].isalpha():
        stem = f"p{stem}"
    stem = stem[: 63 - len(digest)]
    return f"{_SERVICE_ID}.{stem}{digest}"


def daemon_descriptor() -> Mapping[str, Mapping[str, object]]:
    """Build the side-effect-free launch descriptor for the active profile."""
    profile = current_profile()
    port = resolve_http_port()
    pid_file = resolve_pid_file()
    environment = {"AXM_PROFILE": profile}
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
    return {_service_id(profile): service}
