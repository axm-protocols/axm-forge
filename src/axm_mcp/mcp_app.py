"""AXM MCP Server - FastMCP Application.

This module exposes the four agent-facing tools:
- init: Start protocol execution
- resume: Resume a persisted session after MCP restart
- check: Submit task outputs for validation
- read: Read resources by URI
"""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from axm.catalog import ResourceCatalog
from axm.runtime.errors import (
    InvalidURIError,
    SessionNotFoundError,
)
from axm.runtime.orchestrator import ProtocolOrchestrator

# FastMCP server instance
mcp = FastMCP("axm-mcp")

# Global orchestrator instance (will be initialized with catalog)
_orchestrator: ProtocolOrchestrator | None = None


def configure(catalog: ResourceCatalog, sessions_path: Path) -> None:
    """Configure the MCP server with a catalog.

    Args:
        catalog: Protocol catalog for loading definitions.
        sessions_path: Path for session persistence.
    """
    global _orchestrator
    _orchestrator = ProtocolOrchestrator(
        catalog=catalog,
        sessions_path=sessions_path,
    )


def get_orchestrator() -> ProtocolOrchestrator:
    """Get the configured orchestrator.

    Raises:
        RuntimeError: If configure() was not called.
    """
    if _orchestrator is None:
        msg = "MCP server not configured. Call configure() first."
        raise RuntimeError(msg)
    return _orchestrator


@mcp.tool()
def init(protocol_name: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Start a new protocol execution.

    Args:
        protocol_name: Name of the protocol to execute.
        inputs: Optional initial user inputs.

    Returns:
        Dict containing:
        - session_id: Unique session identifier
        - status: Current status ("awaiting")
        - briefing: First task briefing
    """
    orchestrator = get_orchestrator()
    return orchestrator.init(
        protocol_name=protocol_name,
        inputs=inputs or {},
    )


@mcp.tool()
def check(session_id: str, outputs: dict[str, Any]) -> dict[str, Any]:
    """Submit task outputs for validation.

    Args:
        session_id: Session identifier from init().
        outputs: Task outputs to validate.

    Returns:
        Dict containing:
        - status: "awaiting" (next task), "complete", or "retry"
        - briefing: Next task briefing (if status="awaiting")
        - feedback: Validation feedback (if status="retry")
    """
    orchestrator = get_orchestrator()
    return orchestrator.check(
        session_id=session_id,
        outputs=outputs,
    )


@mcp.tool()
def resume(session_id: str) -> dict[str, Any]:
    """Resume an existing session from disk.

    Args:
        session_id: Session identifier from init().

    Returns:
        Dict containing:
        - session_id: Unique session identifier
        - status: Current status ("awaiting")
        - briefing: Next task briefing
    """
    orchestrator = get_orchestrator()
    return orchestrator.resume(session_id=session_id)


@mcp.tool()
def read(session_id: str, uri: str) -> Any:
    """Read a resource by URI.

    Supported URI schemes:
    - context:{key} - Read from session context
    - knowledge:{path} - Read knowledge item
    - artifact:{path} - Read artifact file

    Args:
        session_id: Session identifier from init().
        uri: Resource URI.

    Returns:
        Resource content.
    """
    orchestrator = get_orchestrator()

    # Validate session exists
    if session_id not in orchestrator._sessions:
        raise SessionNotFoundError(session_id)

    # Parse URI
    if ":" not in uri:
        raise InvalidURIError(uri, "missing scheme")

    scheme, path = uri.split(":", 1)

    if scheme == "context":
        return orchestrator.read_context(session_id, path)
    elif scheme == "knowledge":
        return orchestrator.read_knowledge(path)
    elif scheme == "artifact":
        return orchestrator.read_artifact(session_id, path)
    elif scheme == "role":
        return orchestrator.read_role(path)
    else:
        raise InvalidURIError(uri, f"unknown scheme '{scheme}'")


# Entry point for MCP CLI
def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
