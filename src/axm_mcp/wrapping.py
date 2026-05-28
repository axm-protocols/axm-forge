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
from typing import TYPE_CHECKING, Protocol, cast

from axm_mcp.concurrency import KeyedLock

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


class _AnyWrapper(Protocol):
    """Sync or async tool wrapper handed to ``mcp.tool()``."""

    __doc__: str | None

    def __call__(
        self, **kwargs: object
    ) -> _WrapperResult | Awaitable[_WrapperResult]: ...


def log_external_step(
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
        log_external_step(ctx.name, kwargs, success, output_str, duration_ms)
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
    _plain_tool = cast("PlainTool", tool)

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
    _tool_like = cast("ToolLike", tool)

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
