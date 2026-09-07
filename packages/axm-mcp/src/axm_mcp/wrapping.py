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
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from axm.tools.write_scope import WriteContract

from axm_mcp.concurrency import _DEFAULT_TIMEOUT, KeyedLock
from axm_mcp.session_contracts import UnboundSessionError

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
    write_contract_resolver: Callable[[], WriteContract | None]
    shared_mode: bool


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


def _failure_text(result: ToolResultLike, text: str) -> str:
    """Prefix a failing tool's own ``text`` with a status line it cannot forge.

    The status line is composed here, never by the tool: whatever a failing
    ``ToolResult`` puts in ``text`` — including a cheerful "all good" — the
    reader still sees a leading ``✗`` and the ``error``. That is the invariant
    the success-gated short-circuit used to buy by discarding ``text``
    altogether, at the cost of throwing away every diagnostic a tool had
    rendered for its failure paths.

    ``hint`` is appended when present, since ``flatten_result`` surfaces it on
    the dict path and it would otherwise be the one envelope key a text
    rendering silently drops. The status line itself is skipped only when the
    tool's own *first* line already quotes the error verbatim - several tools
    open with a ``name | X | {error}`` header of their own, and repeating it
    makes a reader hunt for a difference that is not there. Scoping that check
    to the first line keeps the invariant honest: an error string appearing
    further down (in a diagnostic body, or a quoted anchor) does not suppress
    the marker, so a failure never arrives unmarked.
    """
    error = str(getattr(result, "error", None) or "failed")
    first = text.partition("\n")[0]
    lines = [text] if error in first else [f"✗ {error}", text]
    hint = getattr(result, "hint", None)
    if hint and str(hint) not in text:
        lines.append(f"hint: {hint}")
    return "\n".join(lines)


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


def _write_refusal(
    ctx: _WrapperCtx,
    tool_input: dict[str, object],
) -> dict[str, object] | None:
    """Resolve and enforce the current session's write perimeter."""
    from axm.tools.write_scope import decide_write_access

    try:
        contract = ctx.write_contract_resolver()
    except UnboundSessionError as exc:
        if not ctx.shared_mode:
            raise
        reason = str(exc)
        logger.warning("Refusing write tool %s: %s", ctx.name, reason)
        return {"success": False, "error": reason}

    if contract is None and ctx.shared_mode:
        reason = f"shared mode refused {ctx.name}: no write contract is attached"
        logger.warning("Refusing write tool %s: %s", ctx.name, reason)
        return {"success": False, "error": reason}

    decision = decide_write_access(contract, ctx.name, tool_input)
    if decision.allowed:
        return None
    return {"success": False, "error": decision.reason}


def _build_plain_wrapper(ctx: _WrapperCtx, tool: ToolEntry) -> _SyncWrapper:
    """Build the wrapper for a plain dispatcher function."""
    _plain_tool = cast("PlainTool", tool)

    def _wrapper(**kwargs: object) -> dict[str, object] | str:
        refusal = _write_refusal(ctx, kwargs)
        if refusal is not None:
            return refusal
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
        refusal = _write_refusal(ctx, kwargs)
        if refusal is not None:
            return refusal
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
        if isinstance(text, str) and (success or text):
            payload = text if success else _failure_text(result, text)
            _trace_step(ctx, kwargs, success, payload, start_ns)
            return payload
        output = flatten_result(result)
        _trace_step(ctx, kwargs, success, str(output), start_ns)
        return output

    return _wrapper


_write_lock = KeyedLock()


def _select_lock(
    name: str,
    kwargs: dict[str, object],
) -> tuple[KeyedLock, tuple[str, ...]] | None:
    """Return the ``(lock, key_param)`` for a tool, or ``None``."""
    if name.startswith("protocol_"):
        key = _normalize_lock_key(kwargs.get("session_id"))
        return _session_lock, (key,) if key is not None else ()
    if name.startswith("git_"):
        key = _normalize_lock_key(kwargs.get("path"))
        return _git_lock, (key,) if key is not None else ()
    if name in {"write_file", "edit_file"}:
        key = _normalize_lock_key(kwargs.get("path"))
        return _write_lock, (key,) if key is not None else ()
    if name != "batch_edit":
        return None

    root = kwargs.get("path")
    operations = kwargs.get("operations")
    if not isinstance(root, str) or not isinstance(operations, list):
        return _write_lock, ()

    keys: set[str] = set()
    for operation in cast("list[object]", operations):
        if not isinstance(operation, dict):
            continue
        file = cast("dict[object, object]", operation).get("file")
        if not isinstance(file, str):
            continue
        key = _normalize_lock_key(str(Path(root, file)))
        if key is not None:
            keys.add(key)
    return _write_lock, tuple(sorted(keys))


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

    async def _async_wrapper(**kwargs: object) -> dict[str, object] | str:
        if not _HTTP_MODE:
            return wrapper(**kwargs)
        selected = _select_lock(name, kwargs)
        if selected is None or not selected[1]:
            return await asyncio.to_thread(wrapper, **kwargs)
        lock, keys = selected
        waiting_key = keys[0]
        try:
            async with AsyncExitStack() as stack:
                for key in keys:
                    waiting_key = key
                    await stack.enter_async_context(lock(key))
                return await asyncio.to_thread(wrapper, **kwargs)
        except TimeoutError as exc:
            logger.warning(
                "Tool %r timed out acquiring lock %r: %s",
                name,
                waiting_key,
                exc,
            )
            return {
                "success": False,
                "error": (
                    f"{name}: resource {waiting_key!r} busy "
                    f"(lock timeout after {_DEFAULT_TIMEOUT}s); retry shortly"
                ),
            }

    _async_wrapper.__doc__ = wrapper.__doc__
    return _async_wrapper


def build_wrappers(
    name: str,
    tool: ToolEntry,
    *,
    shared_mode: bool = False,
    write_contract_resolver: Callable[[], WriteContract | None] | None = None,
) -> tuple[_SyncWrapper, _AnyWrapper]:
    """Build the ``(sync, async)`` wrapper pair for one tool.

    The single construction seam shared by the direct MCP registration path
    (:func:`axm_mcp.discovery.register_one`) and the facade path
    (:class:`axm_mcp.facade.catalog.ToolCatalog`). Both callers pass the same
    shared-mode flag and per-request write-contract resolver, so write-scope
    enforcement cannot diverge between exposure routes. In dedicated mode,
    omitting the resolver preserves the environment-backed fallback. The same
    wrappers also keep kwarg unwrapping, tracing, flattening and locking aligned.

    Returns:
        ``(sync_wrapper, async_wrapper)`` where the sync wrapper carries the
        trace/flatten/exception contract and the async wrapper adds the HTTP
        ``to_thread`` offload plus the optional per-key lock.
    """
    resolver: Callable[[], WriteContract | None]
    if write_contract_resolver is None:
        from axm.tools.write_scope import write_contract_from_env

        write_contract_from_env()
        resolver = write_contract_from_env
    else:
        resolver = write_contract_resolver
    is_plain = callable(tool) and not hasattr(tool, "execute")
    # Protocol tools already trace via orchestrator.run_tool()
    ctx = _WrapperCtx(
        name=name,
        should_trace=not name.startswith("protocol_"),
        write_contract_resolver=resolver,
        shared_mode=shared_mode,
    )
    base_sync_wrapper = (
        _build_plain_wrapper(ctx, tool) if is_plain else _build_tool_wrapper(ctx, tool)
    )

    sync_wrapper = base_sync_wrapper

    exec_doc = getattr(getattr(tool, "execute", tool), "__doc__", None)
    sync_wrapper.__doc__ = exec_doc or f"Execute {name} tool."
    async_wrapper = _wrap_with_lock(sync_wrapper, name)
    return sync_wrapper, async_wrapper
