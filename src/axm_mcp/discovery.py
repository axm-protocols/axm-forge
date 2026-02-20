from __future__ import annotations

import importlib.metadata
import inspect
import logging
from typing import Any, Protocol, runtime_checkable

__all__ = ["_collect_dispatcher_params", "discover_tools", "register_tools"]

logger = logging.getLogger(__name__)

_EP_GROUP = "axm.tools"


@runtime_checkable
class ToolLike(Protocol):
    """Minimal protocol for AXMTool-compatible objects."""

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        ...

    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given keyword arguments."""
        ...


def discover_tools() -> dict[str, Any]:
    """Discover and instantiate all AXMTool entry points.

    Supports both ``AXMTool`` subclasses (instantiated) and plain
    dispatcher functions (used as-is).

    Returns:
        Dict mapping tool name → tool instance or callable.
    """
    tools: dict[str, Any] = {}

    for ep in importlib.metadata.entry_points(group=_EP_GROUP):
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


def register_tools(
    mcp: Any,
    tools: dict[str, Any],
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

    # Register the `list_tools` meta-tool
    _register_list_tools(mcp, tools, extra_tools or {})


def _find_actions_dict(
    module: Any | None,
) -> dict[str, Any] | None:
    """Find a ``_*_ACTIONS`` dict on *module*."""
    if module is None:
        return None
    for attr_name in dir(module):
        if attr_name.endswith("_ACTIONS"):
            candidate = getattr(module, attr_name, None)
            if isinstance(candidate, dict):
                return candidate
    return None


def _union_subfn_params(
    actions_dict: dict[str, Any],
) -> dict[str, inspect.Parameter]:
    """Collect all typed params from sub-functions, made optional."""
    seen: dict[str, inspect.Parameter] = {}
    for sub_fn in actions_dict.values():
        try:
            sub_sig = inspect.signature(sub_fn)
        except (ValueError, TypeError):
            continue
        for p in sub_sig.parameters.values():
            if p.name == "self" or p.kind == inspect.Parameter.VAR_KEYWORD:
                continue
            if p.name not in seen:
                default = (
                    p.default if p.default is not inspect.Parameter.empty else None
                )
                seen[p.name] = p.replace(default=default)
    return seen


def _collect_dispatcher_params(
    fn: Any,
    *,
    override_module: Any | None = None,
) -> list[inspect.Parameter] | None:
    """Collect union of typed params from dispatcher sub-functions.

    A *dispatcher* is a function with ``action: str`` + ``**kwargs``
    that routes to sub-functions stored in a module-level ``_*_ACTIONS``
    dict.  This helper introspects all sub-functions and returns the
    union of their parameters (all made optional).

    Args:
        fn: The dispatcher function to introspect.
        override_module: Module to search for ``_*_ACTIONS`` dict.
            If *None*, uses ``inspect.getmodule(fn)``.

    Returns:
        List of ``inspect.Parameter`` if *fn* is a dispatcher, else *None*.
    """
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return None

    params = list(sig.parameters.values())

    # Detect dispatcher pattern: has 'action' param + VAR_KEYWORD
    has_action = any(p.name == "action" for p in params)
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    if not (has_action and has_varkw):
        return None

    # Find the _ACTIONS dict by convention
    module = override_module or inspect.getmodule(fn)
    actions_dict = _find_actions_dict(module)
    if not actions_dict:
        return None

    # Collect + build final: action (required) + sub-fn params (optional)
    seen = _union_subfn_params(actions_dict)
    action_param = next(p for p in params if p.name == "action")
    return [action_param, *sorted(seen.values(), key=lambda p: p.name)]


def _register_one(
    mcp: Any,
    name: str,
    tool: Any,
    *,
    override_module: Any | None = None,
) -> None:
    """Register a single tool, capturing in closure.

    Supports both ``AXMTool`` instances (with ``.execute()``) and plain
    dispatcher functions.  Sets the typed signature on the wrapper
    **before** handing it to ``mcp.tool()``, so FastMCP generates the
    correct JSON-Schema for the tool's parameters.

    For *dispatcher* functions (``action`` + ``**kwargs``), introspects
    sub-functions to build a union of all their typed parameters.

    Args:
        mcp: FastMCP server instance.
        name: Tool name for MCP registration.
        tool: Tool instance or plain function.
        override_module: For testing — module to search for ``_*_ACTIONS``.
    """
    is_plain = callable(tool) and not hasattr(tool, "execute")
    exec_fn: Any = tool if is_plain else tool.execute

    if is_plain:

        def _wrapper(**kwargs: Any) -> dict[str, Any]:
            # MCP may nest action args inside a "kwargs" key — unwrap.
            if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
                nested = kwargs.pop("kwargs")
                kwargs.update(nested)
            result: dict[str, Any] = tool(**kwargs)
            return result

    else:

        def _wrapper(**kwargs: Any) -> dict[str, Any]:
            # MCP may nest action args inside a "kwargs" key — unwrap.
            if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
                nested = kwargs.pop("kwargs")
                kwargs.update(nested)
            result = tool.execute(**kwargs)
            output: dict[str, Any] = {"success": result.success, **result.data}
            if result.error:
                output["error"] = result.error
            return output

    # Copy docstring.
    _wrapper.__doc__ = exec_fn.__doc__ or f"Execute {name} tool."

    # For dispatchers (action + **kwargs), build union of sub-fn params.
    # For regular tools, strip 'self' and **kwargs.
    try:
        union_params = _collect_dispatcher_params(
            exec_fn, override_module=override_module
        )
        if union_params is not None:
            params = union_params
        else:
            exec_sig = inspect.signature(exec_fn)
            params = [
                p
                for p in exec_sig.parameters.values()
                if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
            ]
        _wrapper.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            parameters=params,
            return_annotation=dict[str, Any],
        )
    except (ValueError, TypeError):
        pass  # Fall back to generic **kwargs if introspection fails

    # Register AFTER setting the signature so FastMCP sees it.
    mcp.tool(name=name)(_wrapper)


def _get_tool_doc(tool: Any) -> str:
    """Extract the first-line docstring from a tool or plain callable."""
    if callable(tool) and not hasattr(tool, "execute"):
        doc = tool.__doc__ or ""
    else:
        doc = getattr(tool.execute, "__doc__", None) or ""
    return doc.strip().split("\n")[0]


def _register_list_tools(
    mcp: Any,
    tools: dict[str, Any],
    extra_tools: dict[str, str],
) -> None:
    """Register the list_tools meta-tool."""

    @mcp.tool(name="list_tools")  # type: ignore[untyped-decorator]
    def _list_tools(**kwargs: Any) -> dict[str, Any]:
        """List all available AXM tools with their names and descriptions."""
        tool_list = []
        for name, tool in sorted(tools.items()):
            tool_list.append({"name": name, "description": _get_tool_doc(tool)})
        for name, desc in sorted(extra_tools.items()):
            tool_list.append({"name": name, "description": desc})
        tool_list.sort(key=lambda t: t["name"])
        return {"tools": tool_list, "count": len(tool_list)}

    logger.info("Registered meta-tool: list_tools")
