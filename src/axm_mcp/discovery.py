"""Auto-discovery of tool entry points for MCP registration.

Scans ``axm.tools`` entry points from all installed packages
(e.g. ``axm``, ``axm-bib``, ``axm-formal``) and registers each tool
as an MCP tool callable.

No imports from axm core — uses duck typing via Protocol.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any, Protocol, runtime_checkable

__all__ = ["discover_tools", "register_tools"]

logger = logging.getLogger(__name__)

_EP_GROUP = "axm.tools"


@runtime_checkable
class ToolLike(Protocol):
    """Minimal protocol for AXMTool-compatible objects."""

    @property
    def name(self) -> str: ...

    def execute(self, **kwargs: Any) -> Any: ...


def discover_tools() -> dict[str, Any]:
    """Discover and instantiate all AXMTool entry points.

    Returns:
        Dict mapping tool name → tool instance.
    """
    tools: dict[str, Any] = {}

    for ep in importlib.metadata.entry_points(group=_EP_GROUP):
        try:
            tool_cls = ep.load()
            tool = tool_cls()
            tools[ep.name] = tool
            logger.debug("Discovered tool: %s", ep.name)
        except Exception:
            logger.warning(
                "Failed to load tool entry point: %s",
                ep.name,
                exc_info=True,
            )

    return tools


def register_tools(
    mcp: Any,
    tools: dict[str, Any],
) -> None:
    """Register discovered tools as MCP tool callables.

    Each tool becomes a callable ``tool_name(**kwargs) -> dict``
    that delegates to ``tool.execute(**kwargs)``.

    Args:
        mcp: FastMCP server instance.
        tools: Dict from discover_tools().
    """
    for name, tool in tools.items():
        _register_one(mcp, name, tool)
        logger.info("Registered MCP tool: %s", name)


def _register_one(mcp: Any, name: str, tool: Any) -> None:
    """Register a single tool, capturing in closure."""

    @mcp.tool(name=name)  # type: ignore[untyped-decorator]
    def _wrapper(**kwargs: Any) -> dict[str, Any]:
        # MCP may wrap args as kwargs={"key": "val"} — unwrap.
        if list(kwargs.keys()) == ["kwargs"] and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        result = tool.execute(**kwargs)
        output: dict[str, Any] = {"success": result.success, **result.data}
        if result.error:
            output["error"] = result.error
        return output

    # Give the wrapper a useful docstring from the tool class
    _wrapper.__doc__ = tool.execute.__doc__ or f"Execute {name} tool."
