"""Tool-call wrapping, tracing, and per-key locking runtime.

Builds the synchronous and async wrapper closures handed to FastMCP for
each discovered tool: kwarg unwrapping, implicit-path warnings, external
session tracing, ToolResult flattening, and per-key concurrency locking
(active only in HTTP mode).

This module is a leaf — it imports only ``axm_mcp.concurrency`` at runtime.
Shared structural protocols (``ToolEntry``, ``ToolLike``, ``PlainTool``,
``ToolResultLike``) live in ``axm_mcp.discovery`` and are referenced here
under ``TYPE_CHECKING`` (annotations are strings via
``from __future__ import annotations``) plus string-literal ``cast`` targets,
keeping the runtime import edge one-directional (``discovery`` -> ``wrapping``).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from axm_mcp.concurrency import _DEFAULT_TIMEOUT, KeyedLock

if TYPE_CHECKING:
    from axm_mcp.discovery import (
        PlainTool,
        ToolEntry,
        ToolLike,
        ToolResultLike,
    )

__all__ = [
    "_HTTP_MODE",
    "_WrapperCtx",
    "_build_plain_wrapper",
    "_build_tool_wrapper",
    "_git_lock",
    "_session_lock",
    "_wrap_with_lock",
    "build_wrappers",
    "flatten_result",
    "log_external_step",
]

logger = logging.getLogger(__name__)

# Set to True when the server runs in HTTP/SSE mode (shared process).
# When True, tools that receive path="." get a warning because "." resolves
# to the server's CWD, not the conversation's workspace.
_HTTP_MODE: bool = False

# Per-key locks — active only in HTTP mode (checked at call time).
_session_lock = KeyedLock()  # protocol_* tools, keyed by session_id
_git_lock = KeyedLock()  # git_* tools, keyed by repo path


# Wrapper callables registered with FastMCP.
type _WrapperResult = dict[str, object] | str


class _SyncWrapper(Protocol):
    """Synchronous tool wrapper."""

    __doc__: str | None

    def __call__(self, **kwargs: object) -> _WrapperResult: ...


class _AsyncWrapper(Protocol):
    """Async tool wrapper handed to ``mcp.tool()``.

    Always a coroutine function: in HTTP mode it offloads the sync body to a
    worker thread (and holds the per-key lock when applicable); in stdio mode
    it simply runs the body inline. Being ``async`` regardless keeps a single
    calling convention for both the direct MCP path and ``ToolCatalog.acall``.
    """

    __doc__: str | None

    def __call__(self, **kwargs: object) -> Awaitable[_WrapperResult]: ...


#: Backwards-compatible alias — the wrapper handed to ``mcp.tool()``.
_AnyWrapper = _AsyncWrapper


def log_external_step(
    tool_name: str,
    tool_args: dict[str, object],
    success: bool,
    result_str: str,
    duration_ms: int,
) -> None:
    """Instrumentation seam for non-protocol tool calls.

    Currently a no-op. This is the hook point where an execution engine
    can observe each MCP tool call (name, args, outcome, duration). The
    legacy ``axm-engine`` tracing wiring was removed when engine was
    deprecated; a future ``axm-loom``-based tracer should re-attach here.
    Any implementation MUST swallow its own errors — tracing must never
    break tool execution.
    """
    # TODO(loom): rebrancher le tracing des appels d'outils MCP ici.


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
        log_external_step(ctx.name, kwargs, success, output_str, duration_ms)
    except Exception:  # noqa: S110
        pass  # tracing must never break tool execution


_RESERVED_KEYS = ("success", "error", "hint")


def flatten_result(result: ToolResultLike) -> dict[str, object]:
    """Flatten a ToolResult into a JSON-friendly dict.

    Spreads ``result.data`` first, then sets the envelope keys
    (``success``/``error``/``hint``) deterministically. Any reserved key
    already present in ``result.data`` is relocated to ``data_{key}`` (with a
    warning) so the envelope is never clobbered and the data value is never
    silently lost.
    """
    output: dict[str, object] = dict(getattr(result, "data", None) or {})
    for key in _RESERVED_KEYS:
        if key in output:
            namespaced = f"data_{key}"
            logger.warning(
                "ToolResult.data key %r collides with the envelope; relocating to %r",
                key,
                namespaced,
            )
            output[namespaced] = output.pop(key)
    # ``success`` missing → False (never silently promoted to a passing result).
    output["success"] = bool(getattr(result, "success", False))
    if getattr(result, "error", None):
        output["error"] = result.error
    hint = getattr(result, "hint", None)
    if hint:
        output["hint"] = hint
    return output


def _flatten_exception(name: str, exc: Exception) -> dict[str, object]:
    """Build the flattened AXM error dict for a raised exception."""
    logger.warning("Tool %r raised %s: %s", name, type(exc).__name__, exc)
    return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def _build_plain_wrapper(ctx: _WrapperCtx, tool: ToolEntry) -> _SyncWrapper:
    """Build the wrapper for a plain dispatcher function."""
    _plain_tool = cast("PlainTool", tool)

    def _wrapper(**kwargs: object) -> dict[str, object] | str:
        _unwrap_nested_kwargs(kwargs)
        _warn_implicit_path(ctx.name, kwargs)
        start_ns = time.perf_counter_ns()
        try:
            result: dict[str, object] = _plain_tool(**kwargs)
        except Exception as exc:
            error = _flatten_exception(ctx.name, exc)
            _trace_step(ctx, kwargs, False, str(error), start_ns)
            return error
        _trace_step(ctx, kwargs, True, str(result), start_ns)
        return result

    return _wrapper


def _build_tool_wrapper(ctx: _WrapperCtx, tool: ToolEntry) -> _SyncWrapper:
    """Build the wrapper for an ``AXMTool`` instance."""
    _tool_like = cast("ToolLike", tool)

    def _wrapper(**kwargs: object) -> dict[str, object] | str:
        _unwrap_nested_kwargs(kwargs)
        _warn_implicit_path(ctx.name, kwargs)
        start_ns = time.perf_counter_ns()
        try:
            result = _tool_like.execute(**kwargs)
        except Exception as exc:
            error = _flatten_exception(ctx.name, exc)
            _trace_step(ctx, kwargs, False, str(error), start_ns)
            return error
        # A missing ``success`` attribute is treated as failure (never defaulted
        # to True): a malformed ToolResult-like never silently passes as success.
        success = bool(getattr(result, "success", False))
        text = getattr(result, "text", None)
        if success and isinstance(text, str):
            _trace_step(ctx, kwargs, success, text, start_ns)
            return text
        output = flatten_result(result)
        _trace_step(ctx, kwargs, success, str(output), start_ns)
        return output

    return _wrapper


def _select_lock(name: str) -> tuple[KeyedLock, str] | None:
    """Return the ``(lock, key_param)`` for a tool, or ``None``."""
    if name.startswith("protocol_"):
        return _session_lock, "session_id"
    if name.startswith("git_"):
        return _git_lock, "path"
    return None


def _normalize_lock_key(key: object) -> str | None:
    """Normalise a lock key so equivalent paths share one lock.

    ``/repo``, ``/repo/`` and a relative equivalent must serialise on the
    *same* key or the per-repo lock is illusory. Non-string keys yield
    ``None`` (skip the lock rather than raise): a client passing a malformed
    ``path`` must not crash the wrapper with an ``AssertionError`` in prod.
    """
    if not isinstance(key, str):
        return None
    try:
        return str(Path(key).resolve())
    except (OSError, ValueError):
        return key


def _wrap_with_lock(wrapper: _SyncWrapper, name: str) -> _AnyWrapper:
    """Wrap *wrapper* with a per-key concurrency lock when applicable.

    In HTTP mode the tool always runs on a worker thread via
    ``asyncio.to_thread`` — sync tool bodies must never execute inline on the
    event loop of the shared server, or one slow call (a 3-minute ``verify``)
    freezes ``/health``, keep-alives and every other conversation. A lock is
    additionally held when the tool opts into per-key serialisation
    (``git_*``/``protocol_*``) *and* the keying argument is present. The lock
    timeout (:data:`concurrency._DEFAULT_TIMEOUT`) is flattened into the AXM
    error envelope instead of propagating to FastMCP as a raw protocol error.
    """
    selected = _select_lock(name)

    async def _async_wrapper(**kwargs: object) -> dict[str, object] | str:
        if not _HTTP_MODE:
            return wrapper(**kwargs)
        key = _normalize_lock_key(kwargs.get(selected[1])) if selected else None
        if selected is None or key is None:
            return await asyncio.to_thread(wrapper, **kwargs)
        lock = selected[0]
        try:
            async with lock(key):
                return await asyncio.to_thread(wrapper, **kwargs)
        except TimeoutError as exc:
            logger.warning("Tool %r timed out acquiring lock %r: %s", name, key, exc)
            return {
                "success": False,
                "error": (
                    f"{name}: resource {key!r} busy "
                    f"(lock timeout after {_DEFAULT_TIMEOUT}s); retry shortly"
                ),
            }

    _async_wrapper.__doc__ = wrapper.__doc__
    return _async_wrapper


def build_wrappers(name: str, tool: ToolEntry) -> tuple[_SyncWrapper, _AnyWrapper]:
    """Build the ``(sync, async)`` wrapper pair for one tool.

    The single construction seam shared by the direct MCP registration path
    (:func:`axm_mcp.discovery.register_one`) and the facade path
    (:class:`axm_mcp.facade.catalog.ToolCatalog`). Both invoke the *same*
    wrappers, so kwarg-unwrapping, implicit-path warnings, tracing, exception
    flattening and per-key locking are invariant regardless of whether a tool
    is reached directly or via ``axm_call`` — there is one execution path.

    Returns:
        ``(sync_wrapper, async_wrapper)`` where the sync wrapper carries the
        trace/flatten/exception contract and the async wrapper adds the HTTP
        ``to_thread`` offload plus the optional per-key lock.
    """
    is_plain = callable(tool) and not hasattr(tool, "execute")
    # Protocol tools already trace via orchestrator.run_tool()
    ctx = _WrapperCtx(name=name, should_trace=not name.startswith("protocol_"))
    sync_wrapper = (
        _build_plain_wrapper(ctx, tool) if is_plain else _build_tool_wrapper(ctx, tool)
    )
    exec_doc = getattr(getattr(tool, "execute", tool), "__doc__", None)
    sync_wrapper.__doc__ = exec_doc or f"Execute {name} tool."
    async_wrapper = _wrap_with_lock(sync_wrapper, name)
    return sync_wrapper, async_wrapper
