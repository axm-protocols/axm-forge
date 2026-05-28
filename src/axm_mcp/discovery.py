from __future__ import annotations

import asyncio
import fnmatch
import importlib.metadata
import inspect
import logging
import os
import re
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from axm_mcp.concurrency import KeyedLock

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

__all__ = [
    "_HTTP_MODE",
    "_collect_dispatcher_params",
    "_extract_docstring_params",
    "_git_lock",
    "_is_disabled",
    "_log_external_step",
    "_register_one",
    "_session_lock",
    "discover_tools",
    "register_tools",
]

logger = logging.getLogger(__name__)

_EP_GROUP = "axm.tools"

# Set to True when the server runs in HTTP/SSE mode (shared process).
# When True, tools that receive path="." get a warning because "." resolves
# to the server's CWD, not the conversation's workspace.
_HTTP_MODE: bool = False

# Per-key locks — active only in HTTP mode (checked at call time).
_session_lock = KeyedLock()  # protocol_* tools, keyed by session_id
_git_lock = KeyedLock()  # git_* tools, keyed by repo path


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


class IntrospectableFn(Protocol):
    """Structural protocol for any callable that supports ``inspect.signature``."""

    __doc__: str | None

    def __call__(self, **kwargs: object) -> object: ...


# A discovered tool entry is either a ToolLike instance or a plain callable.
ToolEntry = ToolLike | PlainTool

# Wrapper callables registered with FastMCP.
type _WrapperResult = dict[str, object] | str


class _SyncWrapper(Protocol):
    """Synchronous tool wrapper."""

    __doc__: str | None

    def __call__(self, **kwargs: object) -> _WrapperResult: ...


class _AnyWrapper(Protocol):
    """Sync or async tool wrapper handed to ``mcp.tool()``."""

    __doc__: str | None

    def __call__(
        self, **kwargs: object
    ) -> _WrapperResult | Awaitable[_WrapperResult]: ...


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


def _find_actions_dict(
    module: ModuleType | None,
) -> dict[str, IntrospectableFn] | None:
    """Find a ``_*_ACTIONS`` dict on *module*."""
    if module is None:
        return None
    for attr_name in dir(module):
        if attr_name.endswith("_ACTIONS"):
            candidate = getattr(module, attr_name, None)
            if isinstance(candidate, dict):
                # Runtime guarantee: ``_*_ACTIONS`` always maps str → callable.
                return cast("dict[str, IntrospectableFn]", candidate)
    return None


def _safe_signature(fn: IntrospectableFn) -> inspect.Signature | None:
    """Resolve a signature, falling back to non-evaluated annotations."""
    try:
        return inspect.signature(fn, eval_str=True)
    except (ValueError, TypeError, NameError):
        try:
            return inspect.signature(fn)
        except (ValueError, TypeError):
            return None


def _accumulate_optional_params(
    sig: inspect.Signature,
    seen: dict[str, inspect.Parameter],
) -> None:
    """Add new typed params from *sig* into *seen*, made optional."""
    for p in sig.parameters.values():
        skip = p.name == "self" or p.kind == inspect.Parameter.VAR_KEYWORD
        if skip or p.name in seen:
            continue
        default = p.default if p.default is not inspect.Parameter.empty else None
        seen[p.name] = p.replace(default=default)


def _union_subfn_params(
    actions_dict: dict[str, IntrospectableFn],
) -> dict[str, inspect.Parameter]:
    """Collect all typed params from sub-functions, made optional."""
    seen: dict[str, inspect.Parameter] = {}
    for sub_fn in actions_dict.values():
        sub_sig = _safe_signature(sub_fn)
        if sub_sig is not None:
            _accumulate_optional_params(sub_sig, seen)
    return seen


# Regex: matches "    param_name (optional type): description" or
#        "    param_name: description" in Google-style Args blocks.
_ARG_LINE_RE = re.compile(
    r"^\s{4,}(\w+)"  # param name (indented 4+ spaces)
    r"(?:\s*\(([^)]+)\))?"  # optional (type) in parens
    r"\s*:"  # colon separator
    r"\s*(.*)$",  # description (captured but unused)
)

# Map common docstring type hints to Python annotations.
_TYPE_MAP: dict[str, type[object]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "Path": str,  # paths come as str over MCP
}


_SECTION_END_RE = re.compile(r"^[A-Z]\w*:\s*$")


def _is_section_end(stripped: str) -> bool:
    return (
        bool(stripped)
        and not stripped.startswith("**")
        and ":" in stripped
        and bool(_SECTION_END_RE.match(stripped))
    )


def _resolve_annotation(type_hint: str | None) -> type[object]:
    if not type_hint:
        return inspect.Parameter.empty
    clean_type = type_hint.split(",")[0].strip()
    return _TYPE_MAP.get(clean_type, inspect.Parameter.empty)


def _parse_arg_line(line: str) -> inspect.Parameter | None:
    match = _ARG_LINE_RE.match(line)
    if not match:
        return None
    return inspect.Parameter(
        match.group(1),
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
        annotation=_resolve_annotation(match.group(2)),
    )


def _extract_docstring_params(
    docstring: str | None,
) -> list[inspect.Parameter]:
    """Parse Google-style ``Args:`` section into ``inspect.Parameter`` objects.

    This is the fallback for non-dispatcher tools whose ``execute(**kwargs)``
    has no typed parameters in the signature but documents them in the
    docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        List of keyword-only ``inspect.Parameter`` with default ``None``.
        Empty list if no ``Args:`` section found.
    """
    if not docstring:
        return []

    in_args = False
    params: list[inspect.Parameter] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if stripped in ("Args:", "Keyword Args:"):
            in_args = True
            continue

        if not in_args:
            continue

        if _is_section_end(stripped):
            break

        if stripped.startswith("**"):
            continue

        param = _parse_arg_line(line)
        if param is not None:
            params.append(param)

    return params


def _collect_dispatcher_params(
    fn: IntrospectableFn,
    *,
    override_module: ModuleType | None = None,
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
    sig = _safe_signature(fn)
    if sig is None:
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


def _log_external_step(
    tool_name: str,
    tool_args: dict[str, object],
    success: bool,
    result_str: str,
    duration_ms: int,
) -> None:
    """Log a non-protocol tool call in the active session trace.

    No-op if no session is active, tracing is disabled, or axm-engine
    is not installed. Errors are silently swallowed — tracing must
    never break tool execution.
    """
    try:
        from axm_engine.runtime.orchestrator import get_orchestrator
        from axm_engine.services.tracing.models import hash_content

        orch = get_orchestrator()
        orch.log_external_step(
            tool_name=tool_name,
            tool_args=tool_args,
            result_success=success,
            result_length=len(result_str),
            result_hash=hash_content(result_str),
            duration_ms=duration_ms,
            result_output=result_str,
        )
    except Exception:  # noqa: S110
        pass  # tracing must never break tool execution


@dataclass(frozen=True)
class _WrapperCtx:
    """Per-tool config shared by the wrapper closures."""

    name: str
    should_trace: bool


def _unwrap_nested_kwargs(kwargs: dict[str, object]) -> None:
    """Unwrap MCP-nested action args from a ``kwargs`` key, in place."""
    nested_raw = kwargs.get("kwargs")
    if isinstance(nested_raw, dict):
        kwargs.pop("kwargs")
        kwargs.update(cast("dict[str, object]", nested_raw))


def _warn_implicit_path(tool_name: str, kwargs: dict[str, object]) -> None:
    """Warn when path is '.' or '' in HTTP mode."""
    if _HTTP_MODE and kwargs.get("path") in (".", ""):
        logger.warning(
            "Tool '%s' called with implicit path='.' in HTTP mode. "
            "Pass an explicit absolute path to avoid operating on the "
            "wrong directory.",
            tool_name,
        )


def _trace_step(
    ctx: _WrapperCtx,
    kwargs: dict[str, object],
    success: bool,
    output_str: str,
    start_ns: int,
) -> None:
    """Record a traced step, swallowing any tracing error."""
    if not ctx.should_trace:
        return
    duration_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
    try:
        _log_external_step(ctx.name, kwargs, success, output_str, duration_ms)
    except Exception:  # noqa: S110
        pass  # tracing must never break tool execution


def _flatten_result(result: ToolResultLike) -> dict[str, object]:
    """Flatten a ToolResult into a JSON-friendly dict."""
    output: dict[str, object] = {"success": result.success, **result.data}
    if result.error:
        output["error"] = result.error
    hint = getattr(result, "hint", None)
    if hint:
        output["hint"] = hint
    return output


def _build_plain_wrapper(ctx: _WrapperCtx, tool: ToolEntry) -> _SyncWrapper:
    """Build the wrapper for a plain dispatcher function."""
    _plain_tool = cast(PlainTool, tool)

    def _wrapper(**kwargs: object) -> dict[str, object] | str:
        _unwrap_nested_kwargs(kwargs)
        _warn_implicit_path(ctx.name, kwargs)
        start_ns = time.perf_counter_ns()
        result: dict[str, object] = _plain_tool(**kwargs)
        _trace_step(ctx, kwargs, True, str(result), start_ns)
        return result

    return _wrapper


def _build_tool_wrapper(ctx: _WrapperCtx, tool: ToolEntry) -> _SyncWrapper:
    """Build the wrapper for an ``AXMTool`` instance."""
    _tool_like = cast(ToolLike, tool)

    def _wrapper(**kwargs: object) -> dict[str, object] | str:
        _unwrap_nested_kwargs(kwargs)
        _warn_implicit_path(ctx.name, kwargs)
        start_ns = time.perf_counter_ns()
        result = _tool_like.execute(**kwargs)
        text = getattr(result, "text", None)
        if isinstance(text, str):
            _trace_step(ctx, kwargs, result.success, text, start_ns)
            return text
        output = _flatten_result(result)
        _trace_step(ctx, kwargs, result.success, str(output), start_ns)
        return output

    return _wrapper


def _select_lock(name: str) -> tuple[KeyedLock, str] | None:
    """Return the ``(lock, key_param)`` for a tool, or ``None``."""
    if name.startswith("protocol_"):
        return _session_lock, "session_id"
    if name.startswith("git_"):
        return _git_lock, "path"
    return None


def _wrap_with_lock(wrapper: _SyncWrapper, name: str) -> _AnyWrapper:
    """Wrap *wrapper* with a per-key concurrency lock when applicable."""
    selected = _select_lock(name)
    if selected is None:
        return wrapper
    _lk, _kp = selected

    async def _async_wrapper(**kwargs: object) -> dict[str, object] | str:
        if not _HTTP_MODE:
            return wrapper(**kwargs)
        key = kwargs.get(_kp)
        if key is None:
            return wrapper(**kwargs)
        assert isinstance(key, str)
        async with _lk(key):
            return await asyncio.to_thread(wrapper, **kwargs)

    _async_wrapper.__doc__ = wrapper.__doc__
    return _async_wrapper


def _signature_params(exec_fn: IntrospectableFn) -> list[inspect.Parameter]:
    """Strip ``self`` / ``**kwargs`` from *exec_fn*, falling back to its docstring."""
    try:
        exec_sig = inspect.signature(exec_fn, eval_str=True)
    except Exception:
        exec_sig = inspect.signature(exec_fn)
    params = [
        p
        for p in exec_sig.parameters.values()
        if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
    ]
    return params or _extract_docstring_params(exec_fn.__doc__)


def _apply_signature(
    wrapper: _AnyWrapper,
    exec_fn: IntrospectableFn,
    override_module: ModuleType | None,
) -> None:
    """Set the typed ``__signature__`` so FastMCP builds the right schema."""
    try:
        union_params = _collect_dispatcher_params(
            exec_fn, override_module=override_module
        )
        params = (
            union_params if union_params is not None else _signature_params(exec_fn)
        )
        wrapper.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            parameters=params,
            return_annotation=dict[str, object] | str,
        )
    except (ValueError, TypeError):
        pass  # Fall back to generic **kwargs if introspection fails


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
    _apply_signature(wrapper, exec_fn, override_module)

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
