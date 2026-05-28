from __future__ import annotations

import fnmatch
import importlib.metadata
import logging
import os
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from axm_mcp.schema import (
    IntrospectableFn,
    apply_signature,
)
from axm_mcp.wrapping import (
    _build_plain_wrapper,
    _build_tool_wrapper,
    _wrap_with_lock,
    _WrapperCtx,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

__all__ = [
    "_is_disabled",
    "_register_one",
    "discover_tools",
    "register_tools",
]

logger = logging.getLogger(__name__)

_EP_GROUP = "axm.tools"


def _is_disabled(name: str, patterns: list[str]) -> bool:
    """Check if a tool name matches any disable pattern.

    Supports exact names (``ast_dead_code``) and glob patterns
    (``bib_*``, ``ticket_*``).
    """
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


class ToolResultLike(Protocol):
    """Structural protocol matching ``axm.tools.base.ToolResult``.

    Declared locally to keep ``axm_mcp.discovery`` free of ``axm.*``
    imports — ``axm-mcp`` is a pure discovery shell (enforced by
    ``test_mcp_decoupled.py``).
    """

    success: bool
    data: dict[str, object]
    error: str | None
    hint: str | None
    text: str | None


@runtime_checkable
class ToolLike(Protocol):
    """Minimal protocol for AXMTool-compatible objects."""

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        ...

    def execute(self, **kwargs: object) -> ToolResultLike:
        """Execute the tool with the given keyword arguments."""
        ...


class PlainTool(Protocol):
    """Structural protocol for plain dispatcher tools (callable, no ``execute``)."""

    def __call__(self, **kwargs: object) -> dict[str, object]: ...


# A discovered tool entry is either a ToolLike instance or a plain callable.
ToolEntry = ToolLike | PlainTool


def discover_tools() -> dict[str, ToolEntry]:
    """Discover and instantiate all AXMTool entry points.

    Supports both ``AXMTool`` subclasses (instantiated) and plain
    dispatcher functions (used as-is).

    Tools can be excluded via the ``AXM_DISABLE_TOOLS`` environment
    variable — a comma-separated list of tool names or glob patterns
    (e.g. ``bib_*,ticket_*,ast_dead_code``).

    Returns:
        Dict mapping tool name → tool instance or callable.
    """
    raw = os.environ.get("AXM_DISABLE_TOOLS", "")
    disable_patterns = [p.strip() for p in raw.split(",") if p.strip()]
    if disable_patterns:
        logger.info("AXM_DISABLE_TOOLS: %s", disable_patterns)

    tools: dict[str, ToolEntry] = {}

    for ep in importlib.metadata.entry_points(group=_EP_GROUP):
        if disable_patterns and _is_disabled(ep.name, disable_patterns):
            logger.info("Skipping disabled tool: %s", ep.name)
            continue
        try:
            obj = ep.load()
            if isinstance(obj, type):
                tool = obj()  # AXMTool class → instantiate
            else:
                tool = obj  # plain function → use as-is
            tools[ep.name] = tool
            logger.debug("Discovered tool: %s", ep.name)
        except Exception:
            logger.warning(
                "Failed to load tool entry point: %s",
                ep.name,
                exc_info=True,
            )

    return tools


def register_tools(  # type: ignore[explicit-any]
    mcp: FastMCP,
    tools: dict[str, ToolEntry],
    extra_tools: dict[str, str] | None = None,
) -> None:
    """Register discovered tools as MCP tool callables.

    Each tool becomes a callable ``tool_name(**kwargs) -> dict``
    that delegates to ``tool.execute(**kwargs)``.

    Args:
        mcp: FastMCP server instance.
        tools: Dict from discover_tools().
        extra_tools: Optional dict of manually-registered tool names
            to their descriptions (for list_tools inclusion).
    """
    for name, tool in tools.items():
        _register_one(mcp, name, tool)
        logger.info("Registered MCP tool: %s", name)


def _register_one(  # type: ignore[explicit-any]
    mcp: FastMCP,
    name: str,
    tool: ToolEntry,
    *,
    override_module: ModuleType | None = None,
) -> None:
    """Register a single tool, capturing in closure.

    Supports both ``AXMTool`` instances (with ``.execute()``) and plain
    dispatcher functions.  Sets the typed signature on the wrapper
    **before** handing it to ``mcp.tool()``, so FastMCP generates the
    correct JSON-Schema for the tool's parameters.

    For *dispatcher* functions (``action`` + ``**kwargs``), introspects
    sub-functions to build a union of all their typed parameters.

    When an ``AXMTool`` returns a ``ToolResult`` whose ``text`` attribute
    is not ``None``, the wrapper short-circuits and returns the raw string
    instead of the flattened dict.  FastMCP converts this to a
    ``TextContent`` response, letting the LLM see pre-rendered markdown
    rather than JSON.

    Args:
        mcp: FastMCP server instance.
        name: Tool name for MCP registration.
        tool: Tool instance or plain function.
        override_module: For testing — module to search for ``_*_ACTIONS``.
    """
    is_plain = callable(tool) and not hasattr(tool, "execute")
    exec_fn: IntrospectableFn = (
        cast(IntrospectableFn, tool)
        if is_plain
        else cast(IntrospectableFn, cast(ToolLike, tool).execute)
    )
    # Protocol tools already trace via orchestrator.run_tool()
    ctx = _WrapperCtx(name=name, should_trace=not name.startswith("protocol_"))

    sync_wrapper = (
        _build_plain_wrapper(ctx, tool) if is_plain else _build_tool_wrapper(ctx, tool)
    )
    sync_wrapper.__doc__ = exec_fn.__doc__ or f"Execute {name} tool."

    wrapper = _wrap_with_lock(sync_wrapper, name)
    apply_signature(wrapper, exec_fn, override_module)

    # Register AFTER setting the signature so FastMCP sees it.
    mcp.tool(name=name)(wrapper)


def _get_tool_doc(tool: ToolEntry) -> str:
    """Extract the first-line docstring from a tool or plain callable."""
    if callable(tool) and not hasattr(tool, "execute"):
        doc = tool.__doc__ or ""
    else:
        doc = getattr(cast(ToolLike, tool).execute, "__doc__", None) or ""
    return doc.strip().split("\n")[0]


def _register_list_tools(  # type: ignore[explicit-any]
    mcp: FastMCP,
    tools: dict[str, ToolEntry],
    extra_tools: dict[str, str],
) -> None:
    """Register the list_tools meta-tool."""

    @mcp.tool(name="list_tools")
    def _list_tools(**kwargs: object) -> dict[str, object]:
        """List all available AXM tools with their names and descriptions."""
        tool_list = []
        for name, tool in sorted(tools.items()):
            tool_list.append({"name": name, "description": _get_tool_doc(tool)})
        for name, desc in sorted(extra_tools.items()):
            tool_list.append({"name": name, "description": desc})
        tool_list.sort(key=lambda t: t["name"])
        return {"tools": tool_list, "count": len(tool_list)}

    logger.info("Registered meta-tool: list_tools")
